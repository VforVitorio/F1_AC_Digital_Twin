import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle
from matplotlib.collections import LineCollection
import warnings
from matplotlib.lines import Line2D
warnings.filterwarnings('ignore')


class ACTelemetryVisualizer:
    def __init__(self, csv_file='data/raw/LAPS_OUTPUT/lap_2_telemetry_2025-09-13_16-18-26.csv'):
        self.csv_file = csv_file
        self.df = None
        self.track_x = None
        self.track_z = None
        self.sector_colors_map = {1: 'red', 2: 'blue', 3: 'yellow'}

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

        # Print sector information
        sectors = self.df['CurrentSectorIndex'].unique()
        print(f"   Sectors found: {sorted(sectors)}")

    def prepare_sector_colors(self):
        """
        Create color arrays for track segments based on sector information.

        Notes:
            The telemetry `CurrentSectorIndex` is encoded as 0,1,2 in the CSV,
            while the internal `sector_colors_map` uses keys 1,2,3 (for display).
            We therefore map telemetry values -> display sector by adding 1.

        Returns:
            list: Colors for each track segment based on current sector
        """
        sector_colors = []
        sectors_found = self.df['CurrentSectorIndex'].unique()
        print(f"Debug: Unique sectors in data: {sorted(sectors_found)}")

        for sector in self.df['CurrentSectorIndex']:
            # Map telemetry sector (0..2) -> display sector (1..3)
            display_sector = int(sector) + 1
            color = self.sector_colors_map.get(display_sector, 'gray')
            sector_colors.append(color)

        # Count colors to verify mapping
        color_counts = {}
        for color in sector_colors:
            color_counts[color] = color_counts.get(color, 0) + 1
        print(f"Debug: Color distribution: {color_counts}")

        return sector_colors

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

        Returns:
            tuple: (fig, axes, info_text, sector_times_box)
        """
        fig, axes = plt.subplots(2, 2, figsize=(16, 13))
        fig.subplots_adjust(top=0.65, bottom=0.12, hspace=0.35, wspace=0.3)

        self._add_title_and_info(fig)

        # Central info text (existing blue box) - top center
        info_text = fig.text(
            0.22, 0.88, '', fontsize=12, verticalalignment='center',
            horizontalalignment='center',
            bbox=dict(boxstyle='round,pad=0.8',
                      facecolor='lightblue', alpha=0.95)
        )

        # New sector-times box - top-left of the figure, non-obstructive
        sector_times_box = fig.text(
            0.02, 0.88, '', fontsize=12, verticalalignment='center',
            horizontalalignment='left',
            bbox=dict(boxstyle='round,pad=0.6', facecolor='#f5f7ff',
                      edgecolor='k', alpha=0.95)
        )

        return fig, axes, info_text, sector_times_box

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
        Configure the track position subplot with sector colors.

        Args:
            ax (matplotlib.axes.Axes): Axes object for the track plot
        """
        # Create colored track segments based on sectors
        sector_colors = self.prepare_sector_colors()

        # Create line segments for colored track
        segments = []
        colors = []

        for i in range(len(self.track_x) - 1):
            segment = [[self.track_x[i], self.track_z[i]],
                       [self.track_x[i+1], self.track_z[i+1]]]
            segments.append(segment)
            colors.append(sector_colors[i])

        # Create LineCollection for colored track
        track_collection = LineCollection(segments, colors=colors,
                                          linewidths=4, alpha=0.8)
        ax.add_collection(track_collection)

        ax.set_aspect('equal')
        ax.set_title('Track Position (Colored by Sector)')
        ax.grid(True, alpha=0.3)

        # Add padding
        padding = 0.1
        x_range = np.max(self.track_x) - np.min(self.track_x)
        z_range = np.max(self.track_z) - np.min(self.track_z)

        ax.set_xlim(np.min(self.track_x) - padding * x_range,
                    np.max(self.track_x) + padding * x_range)
        ax.set_ylim(np.min(self.track_z) - padding * z_range,
                    np.max(self.track_z) + padding * z_range)

        # Add sector legend

        legend_elements = [Line2D([0], [0], color='red', lw=4, label='Sector 1'),
                           Line2D([0], [0], color='blue',
                                  lw=4, label='Sector 2'),
                           Line2D([0], [0], color='yellow', lw=4, label='Sector 3')]
        # Legend placed outside the track axis (above, left-aligned) so it does not overlap the circuit
        ax.legend(handles=legend_elements,
                  title='Sectors',
                  loc='lower left',
                  bbox_to_anchor=(0.15, 1.15),
                  ncol=3,
                  frameon=True)

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

    def create_animation_objects(self, ax_track, ax_speed, ax_throttle_brake, ax_gear_rpm, ax_rpm, info_text, sector_times_box):
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
            (self.track_x[0], self.track_z[0]), car_size, color='#00B25D',
            alpha=0.9, zorder=10, edgecolor='black', linewidth=2)
        ax_track.add_patch(car_marker)

        # Lines and text
        trail_line, = ax_track.plot(
            [], [], '#00B25D', linewidth=3, alpha=0.8, zorder=5)
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
            'car_marker': car_marker,
            'trail_line': trail_line,
            'speed_line': speed_line,
            'throttle_line': throttle_line,
            'brake_line': brake_line,
            'gear_line': gear_line,
            'rpm_line': rpm_line,
            'info_text': info_text,
            'sector_times_box': sector_times_box
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
        Update the central "quick info" box (kept compact).

        This box intentionally omits lap time and current sector so that the
        new dedicated sector-times box can contain that information instead.
        """
        if frame >= len(self.df):
            return

        row = self.df.iloc[frame]

        info_text = (f'Speed: {row["Speed_kmh"]:.1f} km/h\n'
                     f'Gear: {int(row["Gear"])} | RPM: {int(row["RPM"])}\n'
                     f'Throttle: {row["Throttle"]:.2f}\n'
                     f'Brake: {row["Brake"]:.2f}\n'
                     f'Steering: {row["Steering"]:.3f}\n'
                     f'Distance: {row["Distance"]:.0f} m')
        objects['info_text'].set_text(info_text)

    def format_ms(self, ms):
        """
        Helper: format milliseconds into M:SS.mmm

        Args:
            ms (int or float or None): milliseconds

        Returns:
            str: formatted string like '1:21.786' or '-' if not available.
        """
        if ms is None or (isinstance(ms, float) and np.isnan(ms)):
            return '-'
        try:
            ms = int(ms)
        except Exception:
            return '-'
        s, ms_rem = divmod(ms, 1000)
        m, s_rem = divmod(s, 60)
        return f'{m}:{s_rem:02d}.{ms_rem:03d}'

    def _get_lap_data(self, row, frame_idx=None):
        """
        Get DataFrame for current lap.

        This helper function extracts telemetry data for the current lap being analyzed.
        It first tries to filter by LapNumberTotal to get accurate lap boundaries.
        If lap number is not available, it falls back to using all available data.

        Args:
            row: Current row data containing lap information
            frame_idx: Optional frame index for fallback (limits data to current position)

        Returns:
            pd.DataFrame: Filtered telemetry data for the current lap
        """
        # Extract lap number from current telemetry row
        current_lap = row.get('LapNumberTotal', None)

        if current_lap is not None:
            # Filter telemetry data to only include rows from the current lap
            # This ensures accurate sector time calculations within lap boundaries
            lap_df = self.df[self.df['LapNumberTotal'] == current_lap]
        else:
            # Fallback strategy when lap number is unavailable
            # Use entire DataFrame or limit to current frame position for better accuracy
            lap_df = self.df if frame_idx is None else self.df[:frame_idx + 1]

        return lap_df

    def _get_lap_start_time(self, lap_df, current_time_ms=None):
        """
        Get lap start time in milliseconds.

        Finds the earliest timestamp in the lap data to establish the starting point
        for all sector time calculations. This is crucial for accurate timing measurements.

        Args:
            lap_df: DataFrame containing lap data with 'iCurrentTime_ms' column
            current_time_ms: Current time as fallback if lap data is invalid

        Returns:
            int or None: Lap start time in milliseconds, or current_time_ms as fallback
        """
        try:
            # Find the minimum (earliest) timestamp in the lap data
            # This represents when the lap actually started
            return int(lap_df['iCurrentTime_ms'].min())
        except Exception:
            # Fallback to current time if lap data is corrupted or missing timestamps
            return current_time_ms

    def _calculate_sector_1_time(self, lap_df, lap_start_ms):
        """
        Calculate sector 1 time from lap data.

        Finds the first occurrence where CurrentSectorIndex transitions to 1,
        indicating the end of sector 1. The sector time is calculated as the
        difference between this transition point and the lap start.

        Args:
            lap_df: DataFrame containing lap data with sector indices
            lap_start_ms: Lap start time in milliseconds for reference

        Returns:
            int or None: Sector 1 time in milliseconds, None if sector not completed
        """
        try:
            # Find the first row where driver enters sector 2 (CurrentSectorIndex == 1)
            # This marks the end of sector 1 completion
            end_s1_row = lap_df[lap_df['CurrentSectorIndex'] == 1].iloc[0]
            end_s1_ms = int(end_s1_row['iCurrentTime_ms'])

            # Calculate sector 1 time: end timestamp - lap start timestamp
            return end_s1_ms - lap_start_ms if lap_start_ms is not None else None
        except Exception:
            # Return None if sector 1 hasn't been completed yet or data is missing
            return None

    def _calculate_sector_2_time(self, lap_df, lap_start_ms, s1_time):
        """
        Calculate sector 2 time from lap data.

        Finds the first occurrence where CurrentSectorIndex transitions to 2,
        indicating the end of sector 2. The calculation depends on whether
        sector 1 time is available for accurate cumulative timing.

        Args:
            lap_df: DataFrame containing lap data with sector indices
            lap_start_ms: Lap start time in milliseconds for reference
            s1_time: Sector 1 time in milliseconds (may be None)

        Returns:
            int or None: Sector 2 time in milliseconds, None if sector not completed
        """
        try:
            # Find the first row where driver enters sector 3 (CurrentSectorIndex == 2)
            # This marks the end of sector 2 completion
            end_s2_row = lap_df[lap_df['CurrentSectorIndex'] == 2].iloc[0]
            end_s2_ms = int(end_s2_row['iCurrentTime_ms'])

            if s1_time is not None:
                # Preferred calculation: subtract lap start + sector 1 time
                # This gives us the pure sector 2 time
                return end_s2_ms - (lap_start_ms + s1_time)
            else:
                # Fallback calculation when sector 1 time is unavailable
                # Less accurate but still provides sector 2 timing data
                return end_s2_ms - lap_start_ms if lap_start_ms is not None else None
        except Exception:
            # Return None if sector 2 hasn't been completed yet or data is missing
            return None

    def _calculate_sector_3_time(self, lap_df, lap_start_ms, s1_time, s2_time):
        """
        Calculate sector 3 time from lap data.

        Sector 3 is more complex as it ends when the lap completes, marked by
        a reset to CurrentSectorIndex == 0. This function looks for the first
        sector reset after sector 2 completion to determine sector 3 timing.

        Args:
            lap_df: DataFrame containing lap data with sector indices
            lap_start_ms: Lap start time in milliseconds for reference
            s1_time: Sector 1 time in milliseconds (needed for cumulative calculation)
            s2_time: Sector 2 time in milliseconds (needed for cumulative calculation)

        Returns:
            int or None: Sector 3 time in milliseconds, None if sector not completed
        """
        try:
            # Only calculate if we have both sector 1 and 2 times for accuracy
            if s2_time is not None:
                # Calculate the timestamp when sector 2 ended (sector 3 started)
                end_s2_ms = lap_start_ms + s1_time + s2_time

                # Look for telemetry data after sector 2 completion
                later = lap_df[lap_df['iCurrentTime_ms'] > end_s2_ms]

                # Find the first reset to sector 0, indicating lap completion
                later_reset = later[later['CurrentSectorIndex'] == 0]

                if not later_reset.empty:
                    # Calculate sector 3 time: lap end - sector 2 end
                    lap_end_ms = int(later_reset.iloc[0]['iCurrentTime_ms'])
                    return lap_end_ms - end_s2_ms
        except Exception:
            # Exception handling for data corruption or incomplete laps
            pass

        # Return None if calculation fails or prerequisites aren't met
        return None

    def _apply_last_sector_time_fallback(self, row, s1, s2, s3):
        """
        Apply fallback using LastSectorTime_ms for missing sector times.

        When primary sector time calculations fail (due to data corruption or 
        incomplete sectors), this function attempts to use the LastSectorTime_ms
        field as a backup data source. It determines which sector was last
        completed based on the current sector index.

        Args:
            row: Current telemetry row data containing LastSectorTime_ms
            s1, s2, s3: Current sector times (may be None if calculation failed)

        Returns:
            tuple: Updated (s1, s2, s3) with fallback values applied where possible
        """
        try:
            # Extract the LastSectorTime_ms field from telemetry data
            last_sector_time_ms = row.get('LastSectorTime_ms', None)

            # Validate that the fallback data is available and not corrupted
            if last_sector_time_ms is not None and not (isinstance(last_sector_time_ms, float) and np.isnan(last_sector_time_ms)):
                # Determine which sector was most recently completed
                # 0..2 (telemetry format)
                current_sector_raw = int(row['CurrentSectorIndex'])

                # Calculate the display sector number (1..3) of the last completed sector
                # Formula accounts for circular sector progression: 0->1->2->0
                last_completed_display = ((current_sector_raw - 1) % 3) + 1
                idx = last_completed_display - 1  # Convert to 0-based index for array access

                # Apply fallback value to the appropriate sector if it's missing
                if idx == 0 and s1 is None:
                    s1 = int(last_sector_time_ms)
                elif idx == 1 and s2 is None:
                    s2 = int(last_sector_time_ms)
                elif idx == 2 and s3 is None:
                    s3 = int(last_sector_time_ms)
        except Exception:
            # Silently handle any errors in fallback processing
            # Better to return partial data than crash the visualization
            pass

        return s1, s2, s3

    def compute_sector_times_for_lap(self, frame_idx):
        """
        Compute approximate sector times (in ms) for the current lap at the
        provided frame index.

        This is the main entry point for sector time calculation. It orchestrates
        the entire process by calling helper functions in logical order and
        applying fallback strategies when needed.

        Returns:
            list: [s1_ms or None, s2_ms or None, s3_ms or None]
        """
        # Extract telemetry data for current frame position
        row = self.df.iloc[frame_idx]

        # Step 1: Get lap data and validate it's not empty
        lap_df = self._get_lap_data(row)
        if lap_df.empty:
            return [None, None, None]

        # Step 2: Establish lap timing baseline
        lap_start_ms = self._get_lap_start_time(lap_df)

        # Step 3: Calculate each sector time using dedicated functions
        # These functions handle sector boundary detection and timing calculations
        s1 = self._calculate_sector_1_time(lap_df, lap_start_ms)
        s2 = self._calculate_sector_2_time(lap_df, lap_start_ms, s1)
        s3 = self._calculate_sector_3_time(lap_df, lap_start_ms, s1, s2)

        # Step 4: Apply fallback strategy for any missing sector times
        # Uses LastSectorTime_ms as backup data source
        s1, s2, s3 = self._apply_last_sector_time_fallback(row, s1, s2, s3)

        return [s1, s2, s3]

    def _get_completed_sector_times(self, lap_df, lap_start_ms):
        """
        Get completed sector times from lap data.

        This convenience function calculates all three sector times in one call,
        ensuring consistent calculation methodology across all sectors.

        Args:
            lap_df: DataFrame containing lap data with sector transitions
            lap_start_ms: Lap start time in milliseconds for reference

        Returns:
            tuple: (s1_final, s2_final, s3_final) - completed sector times or None if not completed
        """
        # Use existing calculation functions to maintain consistency
        s1_final = self._calculate_sector_1_time(lap_df, lap_start_ms)
        s2_final = self._calculate_sector_2_time(
            lap_df, lap_start_ms, s1_final)
        s3_final = self._calculate_sector_3_time(
            lap_df, lap_start_ms, s1_final, s2_final)

        return s1_final, s2_final, s3_final

    def _format_sector_1_display(self, current_time_ms, lap_start_ms, s1_final, s2_final, s3_final):
        """
        Format sector times when currently in sector 1.

        During sector 1, only the current sector time is dynamic (increasing).
        Sectors 2 and 3 haven't started yet, so they display as zero.

        Returns:
            tuple: (s1_str, s2_str, s3_str) formatted display strings
        """
        # Calculate elapsed time in current sector 1
        current_sector_time = current_time_ms - lap_start_ms

        # Format current sector 1 time (dynamic, increasing)
        s1_str = self.format_ms(
            current_sector_time) if current_sector_time >= 0 else '0:00.000'

        # Sectors 2 and 3 haven't started - display as zero
        s2_str = '0:00.000'
        s3_str = '0:00.000'
        return s1_str, s2_str, s3_str

    def _format_sector_2_display(self, current_time_ms, lap_start_ms, s1_final, s2_final, s3_final):
        """
        Format sector times when currently in sector 2.

        During sector 2, sector 1 shows its final completed time, sector 2 
        shows dynamic increasing time, and sector 3 remains at zero.

        Returns:
            tuple: (s1_str, s2_str, s3_str) formatted display strings
        """
        # Display sector 1 final time (completed) or fallback indicator
        s1_str = self.format_ms(s1_final) if s1_final is not None else '-'

        # Calculate current sector 2 elapsed time
        if s1_final is not None:
            # Preferred: subtract lap start + sector 1 time for accurate sector 2 time
            current_sector_time = current_time_ms - (lap_start_ms + s1_final)
            s2_str = self.format_ms(
                current_sector_time) if current_sector_time >= 0 else '0:00.000'
        else:
            # Fallback: use total elapsed time when sector 1 time is unavailable
            s2_str = self.format_ms(
                current_time_ms - lap_start_ms) if current_time_ms >= lap_start_ms else '0:00.000'

        # Sector 3 hasn't started yet
        s3_str = '0:00.000'
        return s1_str, s2_str, s3_str

    def _format_sector_3_display(self, current_time_ms, lap_start_ms, s1_final, s2_final, s3_final):
        """
        Format sector times when currently in sector 3.

        During sector 3, sectors 1 and 2 show their final completed times,
        while sector 3 shows dynamic increasing time until lap completion.

        Returns:
            tuple: (s1_str, s2_str, s3_str) formatted display strings
        """
        # Display final times for completed sectors 1 and 2
        s1_str = self.format_ms(s1_final) if s1_final is not None else '-'
        s2_str = self.format_ms(s2_final) if s2_final is not None else '-'

        # Calculate current sector 3 elapsed time
        if s1_final is not None and s2_final is not None:
            # Preferred: subtract cumulative time of previous sectors
            current_sector_time = current_time_ms - \
                (lap_start_ms + s1_final + s2_final)
            s3_str = self.format_ms(
                current_sector_time) if current_sector_time >= 0 else '0:00.000'
        else:
            # Fallback: use total elapsed time when previous sector data is incomplete
            s3_str = self.format_ms(
                current_time_ms - lap_start_ms) if current_time_ms >= lap_start_ms else '0:00.000'

        return s1_str, s2_str, s3_str

    def _format_fallback_display(self, s1_final, s2_final, s3_final):
        """
        Format sector times for fallback case.

        Used when the current sector index is invalid or unrecognized.
        Displays available sector times or default zeros for missing data.

        Returns:
            tuple: (s1_str, s2_str, s3_str) formatted display strings
        """
        # Display final sector times if available, otherwise show zeros
        s1_str = self.format_ms(
            s1_final) if s1_final is not None else '0:00.000'
        s2_str = self.format_ms(
            s2_final) if s2_final is not None else '0:00.000'
        s3_str = self.format_ms(
            s3_final) if s3_final is not None else '0:00.000'
        return s1_str, s2_str, s3_str

    def compute_dynamic_sector_times(self, frame_idx):
        """
        Compute dynamic sector times showing progress in real-time.

        This is the main entry point for real-time sector time display.
        It shows completed sector times as final values and the current 
        sector time as a dynamically increasing counter, providing live
        feedback during the visualization.

        Args:
            frame_idx (int): Current frame index in the telemetry data

        Returns:
            tuple: (s1_str, s2_str, s3_str) - Formatted time strings for display
        """
        # Validate frame index bounds
        if frame_idx >= len(self.df):
            return '-', '-', '-'

        # Extract current telemetry data point
        row = self.df.iloc[frame_idx]
        # 0, 1, 2 (telemetry format)
        current_sector_raw = int(row['CurrentSectorIndex'])
        current_time_ms = row.get('iCurrentTime_ms', None)

        # Validate timestamp availability
        if current_time_ms is None:
            return '-', '-', '-'

        # Step 1: Get lap data and establish timing baseline
        lap_df = self._get_lap_data(row, frame_idx)
        if lap_df.empty:
            return '-', '-', '-'

        # Step 2: Calculate lap start time for reference
        lap_start_ms = self._get_lap_start_time(lap_df, current_time_ms)

        # Step 3: Get all completed sector times using existing calculation logic
        s1_final, s2_final, s3_final = self._get_completed_sector_times(
            lap_df, lap_start_ms)

        # Step 4: Format display based on current sector position
        # Each sector has different display logic for dynamic timing
        if current_sector_raw == 0:  # Currently in Sector 1
            return self._format_sector_1_display(current_time_ms, lap_start_ms, s1_final, s2_final, s3_final)
        elif current_sector_raw == 1:  # Currently in Sector 2
            return self._format_sector_2_display(current_time_ms, lap_start_ms, s1_final, s2_final, s3_final)
        elif current_sector_raw == 2:  # Currently in Sector 3
            return self._format_sector_3_display(current_time_ms, lap_start_ms, s1_final, s2_final, s3_final)
        else:
            # Handle invalid or unrecognized sector indices
            return self._format_fallback_display(s1_final, s2_final, s3_final)

    def update_sector_times_box(self, frame, objects):
        """
        Update the sector_times_box text object with dynamic sector times.

        Shows real-time progress of current sector and completed times for finished sectors.
        """
        if frame >= len(self.df):
            return

        row = self.df.iloc[frame]

        time_str = self.format_ms(row.get('iCurrentTime_ms', None))
        current_sector_display = int(row['CurrentSectorIndex']) + 1

        # Get dynamic sector times
        s1_str, s2_str, s3_str = self.compute_dynamic_sector_times(frame)

        best_time_str = self.format_ms(row.get('iBestTime_ms', None))
        last_time_str = self.format_ms(row.get('iLastTime_ms', None))

        box_text = (f'Time: {time_str}\n'
                    f'Current Sector: {current_sector_display}\n'
                    f'Sector 1 Time: {s1_str}\n'
                    f'Sector 2 Time: {s2_str}\n'
                    f'Sector 3 Time: {s3_str}\n'
                    f'Best Time: {best_time_str}\n'
                    f'Last Time: {last_time_str}')
        objects['sector_times_box'].set_text(box_text)

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
        try:
            self.update_sector_times_box(frame, objects)
        except Exception:
            # fail-safe so animation does not stop because of a sector-time edge case
            pass

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
        fig, axes, info_text, sector_times_box = self.create_figure_layout()
        ax_track, ax_speed, ax_throttle_brake, ax_gear_rpm = axes.flatten()

        self.setup_track_plot(ax_track)
        ax_rpm = self.setup_telemetry_plots(
            ax_speed, ax_throttle_brake, ax_gear_rpm)

        # Create animation
        objects = self.create_animation_objects(
            ax_track, ax_speed, ax_throttle_brake, ax_gear_rpm, ax_rpm, info_text, sector_times_box)

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
