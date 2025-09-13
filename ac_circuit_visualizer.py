import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle
import warnings

warnings.filterwarnings('ignore')


class ACTelemetryVisualizer:
    def __init__(self, csv_file='TELEMETRY/LAPS_OUTPUT/lap_2_telemetry.csv'):
        self.csv_file = csv_file
        self.df = None
        self.track_x = None
        self.track_z = None

    def load_telemetry_data(self):
        """
        Load telemetry data from CSV file and analyze basic metrics.

        Reads the telemetry CSV file specified in the constructor and stores it
        in a pandas DataFrame. Prints a summary of the loaded data including
        speed range, total distance, and lap time.

        Returns:
            pd.DataFrame: Loaded telemetry data with all recorded metrics
        """
        print(f"Loading telemetry data from {self.csv_file.split('/')[-1]}...")
        self.df = pd.read_csv(self.csv_file)

        self._print_data_summary()
        return self.df

    def _print_data_summary(self):
        """
        Print a summary of the loaded telemetry data to console.

        Displays key metrics including total data points, speed range,
        total distance covered, and final lap time. Used for debugging
        and data validation purposes.
        """
        print(f"✅ Data loaded: {len(self.df)} points")
        print(
            f"   Speed range: {self.df['Speed_kmh'].min():.1f} - {self.df['Speed_kmh'].max():.1f} km/h")
        print(f"   Distance: {self.df['Distance'].max():.1f} m")
        print(f"   Lap time: {self.df['CurrentLapTime_str'].iloc[-1]}")

    def center_coordinates(self, x, z):
        """
        Center coordinate arrays around their mean values.

        Args:
            x (np.array): X coordinate values
            z (np.array): Z coordinate values

        Returns:
            tuple: Centered (x, z) coordinates as numpy arrays
        """
        return x - np.mean(x), z - np.mean(z)

    def rotate_coordinates(self, x, z, angle_rad):
        """
        Apply 2D rotation transformation to coordinate arrays.

        Args:
            x (np.array): X coordinate values
            z (np.array): Z coordinate values
            angle_rad (float): Rotation angle in radians

        Returns:
            tuple: Rotated (x_rot, z_rot) coordinates as numpy arrays
        """
        x_rot = x * np.cos(angle_rad) - z * np.sin(angle_rad)
        z_rot = x * np.sin(angle_rad) + z * np.cos(angle_rad)
        return x_rot, z_rot

    def calculate_aspect_ratio(self, x, z):
        """
        Calculate the width-to-height aspect ratio of coordinate bounds.

        Args:
            x (np.array): X coordinate values
            z (np.array): Z coordinate values

        Returns:
            float: Aspect ratio (width/height) with small epsilon to avoid division by zero
        """
        width = np.max(x) - np.min(x)
        height = np.max(z) - np.min(z)
        return width / (height + 0.001)

    def optimize_track_layout(self, track_x_raw, track_z_raw):
        """
        Find optimal track orientation by maximizing aspect ratio through rotation.

        Tests different rotation angles (0-180 degrees) to find the orientation
        that maximizes the track's width-to-height ratio for better visualization.

        Args:
            track_x_raw (np.array): Raw X coordinate values from telemetry
            track_z_raw (np.array): Raw Z coordinate values from telemetry

        Returns:
            tuple: Optimized (x, z) coordinates with best orientation
        """
        x_centered, z_centered = self.center_coordinates(
            track_x_raw, track_z_raw)

        best_ratio = 0
        best_rotation = 0
        best_coords = (x_centered, z_centered)

        for angle_deg in range(0, 180, 10):
            angle_rad = np.radians(angle_deg)
            x_rot, z_rot = self.rotate_coordinates(
                x_centered, z_centered, angle_rad)
            ratio = self.calculate_aspect_ratio(x_rot, z_rot)

            if ratio > best_ratio:
                best_ratio = ratio
                best_rotation = angle_deg
                best_coords = (x_rot, z_rot)

        print(
            f"Track optimized: {best_rotation}° rotation, ratio: {best_ratio:.2f}")
        return best_coords

    def prepare_track_data(self):
        """
        Extract track coordinates from telemetry data and optimize layout.

        Processes the X and Z position data from the loaded telemetry DataFrame,
        applies coordinate optimization for better visualization, and stores
        the processed coordinates in instance variables.
        """
        track_x_raw = self.df['X'].values
        track_z_raw = self.df['Z'].values
        self.track_x, self.track_z = self.optimize_track_layout(
            track_x_raw, track_z_raw)

    def create_figure_layout(self):
        """
        Create matplotlib figure with 2x2 subplot layout for telemetry visualization.

        Sets up the main figure window with proper spacing and adds title information
        and info text area for real-time telemetry display.

        Returns:
            tuple: (fig, axes, info_text) - Figure object, axes array, and info text object
        """
        fig, axes = plt.subplots(2, 2, figsize=(16, 13))
        fig.subplots_adjust(top=0.65, bottom=0.12, hspace=0.35, wspace=0.3)

        self._add_title_and_info(fig)

        # Create info text outside the track plot
        info_text = fig.text(0.5, 0.82, '', fontsize=12, verticalalignment='top', horizontalalignment='center',
                             bbox=dict(boxstyle='round,pad=0.8', facecolor='lightblue', alpha=0.9))

        return fig, axes, info_text

    def _add_title_and_info(self, fig):
        """
        Add main title and lap information to the figure.

        Args:
            fig (matplotlib.figure.Figure): Figure object to add titles to
        """
        fig.suptitle("AC Circuit Telemetry Analysis", fontsize=16, y=0.94)

        lap_time = self.df['CurrentLapTime_str'].iloc[-1]
        max_speed = self.df['Speed_kmh'].max()
        tyre_compound = self.df['TyreCompound'].iloc[0]

        info_text = f"Lap Time: {lap_time}  |  Max Speed: {max_speed:.1f} km/h  |  Tyres: {tyre_compound}"
        fig.text(0.5, 0.88, info_text, ha='center',
                 fontsize=12, fontweight='bold')

    def setup_track_plot(self, ax):
        """
        Configure the track position subplot with proper scaling and appearance.

        Args:
            ax (matplotlib.axes.Axes): Axes object for the track plot
        """
        ax.plot(self.track_x, self.track_z, 'gray', linewidth=3, alpha=0.4)
        ax.set_aspect('equal')
        ax.set_title('Track Position')
        ax.grid(True, alpha=0.3)

        # Add padding
        padding = 0.1
        x_range = np.max(self.track_x) - np.min(self.track_x)
        z_range = np.max(self.track_z) - np.min(self.track_z)

        ax.set_xlim(np.min(self.track_x) - padding * x_range,
                    np.max(self.track_x) + padding * x_range)
        ax.set_ylim(np.min(self.track_z) - padding * z_range,
                    np.max(self.track_z) + padding * z_range)

    def setup_telemetry_plots(self, ax_speed, ax_throttle_brake, ax_gear_rpm):
        """
        Configure all telemetry data subplots with appropriate scales and labels.

        Args:
            ax_speed (matplotlib.axes.Axes): Axes for speed plot
            ax_throttle_brake (matplotlib.axes.Axes): Axes for throttle/brake plot
            ax_gear_rpm (matplotlib.axes.Axes): Axes for gear/RPM plot

        Returns:
            matplotlib.axes.Axes: Secondary y-axis for RPM data
        """
        max_distance = self.df['Distance'].max()
        max_speed = self.df['Speed_kmh'].max()
        max_rpm = self.df['RPM'].max()

        # Speed plot
        ax_speed.set_xlim(0, max_distance)
        ax_speed.set_ylim(0, max_speed * 1.05)
        ax_speed.set_title('Speed')
        ax_speed.set_ylabel('Speed (km/h)')
        ax_speed.set_xlabel('Distance (m)')
        ax_speed.grid(True, alpha=0.3)

        # Throttle/Brake plot
        ax_throttle_brake.set_xlim(0, max_distance)
        ax_throttle_brake.set_ylim(-1.1, 1.1)
        ax_throttle_brake.set_title('Throttle & Brake')
        ax_throttle_brake.set_ylabel('Input (0-1)')
        ax_throttle_brake.set_xlabel('Distance (m)')
        ax_throttle_brake.grid(True, alpha=0.3)
        ax_throttle_brake.axhline(y=0, color='black', linestyle='-', alpha=0.3)

        # Gear/RPM plot
        ax_gear_rpm.set_xlim(0, max_distance)
        ax_gear_rpm.set_title('Gear & RPM')
        ax_gear_rpm.set_xlabel('Distance (m)')
        ax_gear_rpm.grid(True, alpha=0.3)

        ax_rpm = ax_gear_rpm.twinx()
        ax_gear_rpm.set_ylabel('Gear', color='blue')
        ax_rpm.set_ylabel('RPM', color='orange')
        ax_gear_rpm.set_ylim(0, self.df['Gear'].max() + 1)
        ax_rpm.set_ylim(0, max_rpm * 1.05)

        return ax_rpm

    def create_animation_objects(self, ax_track, ax_speed, ax_throttle_brake, ax_gear_rpm, ax_rpm, info_text):
        """
        Initialize all visual elements and plot objects for animation.

        Args:
            ax_track (matplotlib.axes.Axes): Track position axes
            ax_speed (matplotlib.axes.Axes): Speed plot axes
            ax_throttle_brake (matplotlib.axes.Axes): Throttle/brake plot axes
            ax_gear_rpm (matplotlib.axes.Axes): Gear plot axes
            ax_rpm (matplotlib.axes.Axes): RPM plot axes (secondary y-axis)
            info_text (matplotlib.text.Text): Text object for real-time info display

        Returns:
            dict: Dictionary containing all animation objects (markers, lines, text)
        """
        # Car marker
        track_range = max(np.max(self.track_x) - np.min(self.track_x),
                          np.max(self.track_z) - np.min(self.track_z))
        car_size = track_range * 0.02
        car_marker = Circle(
            (self.track_x[0], self.track_z[0]), car_size, color='red', alpha=0.9, zorder=10)
        ax_track.add_patch(car_marker)

        # Lines and text
        trail_line, = ax_track.plot(
            [], [], 'red', linewidth=2, alpha=0.6, zorder=5)
        speed_line, = ax_speed.plot([], [], 'blue', linewidth=3, alpha=0.9)
        throttle_line, = ax_throttle_brake.plot(
            [], [], 'green', linewidth=3, alpha=0.9, label='Throttle')
        brake_line, = ax_throttle_brake.plot(
            [], [], 'red', linewidth=3, alpha=0.9, label='Brake')
        gear_line, = ax_gear_rpm.plot(
            [], [], 'blue', linewidth=3, alpha=0.9, marker='o', markersize=4)
        rpm_line, = ax_rpm.plot([], [], 'orange', linewidth=2, alpha=0.9)

        ax_throttle_brake.legend(loc='upper right')

        return {
            'car_marker': car_marker, 'trail_line': trail_line, 'speed_line': speed_line,
            'throttle_line': throttle_line, 'brake_line': brake_line, 'gear_line': gear_line,
            'rpm_line': rpm_line, 'info_text': info_text
        }

    def update_car_position(self, frame, objects):
        """
        Update car marker position and trail on the track plot.

        Args:
            frame (int): Current animation frame number
            objects (dict): Dictionary containing animation objects
        """
        progress = frame / len(self.track_x)
        idx = min(int(progress * (len(self.track_x) - 1)),
                  len(self.track_x) - 1)

        objects['car_marker'].center = (self.track_x[idx], self.track_z[idx])

        # Update trail
        trail_length = min(50, frame)
        if trail_length > 1:
            start_idx = max(0, idx - trail_length)
            end_idx = idx + 1
            objects['trail_line'].set_data(
                self.track_x[start_idx:end_idx], self.track_z[start_idx:end_idx])

    def update_telemetry_lines(self, frame, objects):
        """
        Update all telemetry data line plots with current frame data.

        Args:
            frame (int): Current animation frame number
            objects (dict): Dictionary containing animation objects
        """
        if frame < 1:
            return

        current_data = self.df.iloc[:frame+1]
        distances = current_data['Distance'].values

        objects['speed_line'].set_data(
            distances, current_data['Speed_kmh'].values)
        objects['throttle_line'].set_data(
            distances, current_data['Throttle'].values)
        objects['brake_line'].set_data(
            distances, -current_data['Brake'].values)
        objects['gear_line'].set_data(distances, current_data['Gear'].values)
        objects['rpm_line'].set_data(distances, current_data['RPM'].values)

    def update_info_text(self, frame, objects):
        """
        Update real-time telemetry information display.

        Args:
            frame (int): Current animation frame number
            objects (dict): Dictionary containing animation objects
        """
        if frame >= len(self.df):
            return

        row = self.df.iloc[frame]
        info_text = (f'Speed: {row["Speed_kmh"]:.1f} km/h\n'
                     f'Gear: {row["Gear"]} | RPM: {row["RPM"]}\n'
                     f'Throttle: {row["Throttle"]:.2f}\n'
                     f'Brake: {row["Brake"]:.2f}\n'
                     f'Steering: {row["Steering"]:.3f}\n'
                     f'Distance: {row["Distance"]:.0f}m\n'
                     f'Time: {row["CurrentLapTime_str"]}')
        objects['info_text'].set_text(info_text)

    def animate_frame(self, frame, objects):
        """
        Main animation callback function that updates all visual elements.

        Args:
            frame (int): Current animation frame number
            objects (dict): Dictionary containing all animation objects

        Returns:
            list: List of updated animation objects for matplotlib blitting
        """
        if frame >= len(self.df):
            return []

        self.update_car_position(frame, objects)
        self.update_telemetry_lines(frame, objects)
        self.update_info_text(frame, objects)

        return list(objects.values())

    def run_simulation(self):
        """
        Execute the complete telemetry visualization with animated display.

        Orchestrates the entire visualization process: loads telemetry data,
        prepares track coordinates, sets up matplotlib plots, creates animation
        objects, and starts the real-time animated visualization.

        Returns:
            matplotlib.animation.FuncAnimation: Animation object for the telemetry visualization
        """
        if self.df is None:
            self.load_telemetry_data()

        self.prepare_track_data()

        # Create plots
        fig, axes, info_text = self.create_figure_layout()
        ax_track, ax_speed, ax_throttle_brake, ax_gear_rpm = axes.flatten()

        self.setup_track_plot(ax_track)
        ax_rpm = self.setup_telemetry_plots(
            ax_speed, ax_throttle_brake, ax_gear_rpm)

        # Create animation
        objects = self.create_animation_objects(
            ax_track, ax_speed, ax_throttle_brake, ax_gear_rpm, ax_rpm, info_text)

        print(f"Starting animation with {len(self.df)} frames...")
        anim = animation.FuncAnimation(fig, self.animate_frame, frames=len(self.df),
                                       fargs=(objects,), interval=50, repeat=True, blit=False)

        plt.show()
        return anim


# Main execution
if __name__ == "__main__":
    visualizer = ACTelemetryVisualizer()
    anim = visualizer.run_simulation()

    try:
        input("Press Enter to close the animation...")
    except KeyboardInterrupt:
        print("Animation closed by user")
