# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased][Unreleased]

### Added

- **Intelligent Distance Normalization**: Revolutionary postprocessing algorithm for lap-relative distance calculation
  - Automatic detection of lap boundaries in telemetry data
  - Per-lap distance reset to 0 at lap start for proper analysis
  - Preservation of original absolute distance data alongside normalized values
  - Real-time lap completion detection with performance feedback
  - Comprehensive distance analysis with visual verification tools
- **Advanced Interactive Telemetry Dashboard**: Professional-grade visualization system using Plotly
  - Comprehensive 2×3 grid layout with all key telemetry parameters (Gear, Speed, RPM, Throttle, Brake, Steering)
  - Interactive hover tooltips with precise value display at any distance point
  - Modern color palette with consistent visual identity across all charts
  - Separated throttle and brake visualizations for enhanced clarity
  - Real-time responsive design with zoom, pan, and selection capabilities
- **Interactive Lap Selector**: Dynamic single-lap analysis with ipywidgets integration
  - Live lap selection with instant plot updates
  - Individual parameter analysis with dedicated charts for each metric
  - Gear progression analysis with step-like visualization and integer-only y-axis
  - Engine RPM analysis with precise hover data
  - Separated input analysis (throttle, brake, steering) for detailed driver behavior study
  - Robust fallback system when interactive widgets are unavailable
- **Comprehensive Code Documentation**: Enterprise-level documentation in English
  - Complete function-level docstrings with detailed parameter descriptions
  - Algorithm explanations with practical examples and use cases
  - Inline comments explaining the "why" behind implementation decisions
  - Professional error handling with informative user feedback
  - Technical architecture documentation for maintainability
- **Distance Pattern Analysis Tools**: Advanced tools for understanding lap distance anomalies
  - Automatic explanation of why laps start at non-zero distances (e.g., 17K meters)
  - Visual verification with theoretical lap overlays
  - Comprehensive statistics display with lap length analysis
  - Circuit-specific calculations (Monza: 5,793m reference)

### Enhanced

- **Telemetry Collector Architecture**: Complete overhaul with professional-grade features
  - Comprehensive shared memory connection strategies with multiple namespace fallbacks
  - UTF-16 string decoding with robust error handling for AC's wide character arrays
  - Enhanced lap detection with informative completion notifications
  - Professional signal handling (SIGINT/SIGTERM) for graceful data preservation
  - Expanded CSV export with 20+ telemetry parameters including car coordinates and surface grip
  - Real-time telemetry display with compact, informative format
  - Intelligent postprocessing pipeline that normalizes distance data on save
- **Data Processing Pipeline**: Advanced preprocessing with automatic file discovery
  - Multi-path telemetry file discovery with intelligent recent-file selection
  - Comprehensive column normalization handling various AC export formats
  - Robust data type validation and missing value handling
  - Dynamic distance calculation with fallback strategies
- **Notebook Structure**: Complete restructure with professional analysis workflow
  - English-language documentation throughout with technical precision
  - Modular cell organization for progressive analysis complexity
  - Comprehensive error handling with informative fallback messages
  - Export capabilities for individual lap analysis and external processing

### Technical Improvements

- **Algorithm Optimization**: Efficient lap-relative distance calculation
  - O(n) single-pass algorithm for distance normalization
  - Memory-efficient processing with minimal data duplication
  - Intelligent caching of lap boundary markers
- **Visualization Performance**: Optimized Plotly rendering for large datasets
  - Efficient data point handling for smooth interactive experience
  - Strategic use of line shapes (step-like for gears, smooth for continuous data)
  - Optimized subplot layouts with proper spacing and responsive design
- **Code Quality**: Professional development standards
  - Type hints and comprehensive error handling
  - Consistent naming conventions and code structure
  - Comprehensive logging and user feedback systems
  - Modular architecture for easy extension and maintenance

### Fixed

- **Distance Continuity Issues**: Solved the 17K meter starting distance problem
  - Root cause analysis: AC's cumulative distance across session
  - Solution: Lap-relative distance recalculation during CSV export
  - Implementation: Non-intrusive postprocessing that preserves original data
  - Verification: Visual tools to confirm proper distance normalization
- **Visualization Clarity**: Enhanced readability and interaction
  - Separated overlapping throttle/brake charts for better analysis
  - Improved color contrast and accessibility
  - Consistent styling across all visualizations
  - Better error messages for missing data scenarios

### Comparison with Previous Version

**Previous Implementation (Spanish/Mixed Language):**

- Basic telemetry collection with corrected ctypes structures
- Simple CSV export with timestamp-based filenames
- Matplotlib-based static visualizations
- Manual lap detection and analysis
- Basic shared memory connection handling

**Current Implementation (Professional English):**

- ✅ **Intelligent distance normalization** with automatic lap-relative calculation
- ✅ **Advanced interactive dashboards** with Plotly and hover analytics
- ✅ **Comprehensive documentation** with enterprise-level code quality
- ✅ **Robust error handling** and graceful degradation strategies
- ✅ **Professional visualization** with consistent modern design
- ✅ **Enhanced data export** with detailed statistics and verification
- ✅ **Modular architecture** for easy maintenance and extension

**Migration Benefits:**

- **Data Quality**: Lap distances now start at 0m for proper analysis
- **User Experience**: Interactive visualizations with real-time feedback
- **Code Maintainability**: Professional documentation and error handling
- **Analysis Capabilities**: Advanced tools for driver behavior analysis
- **International Compatibility**: Full English documentation and interfaces

---

## [1.0.0][1.0.0] - 2025-09-12

### Added

- **Assetto Corsa Telemetry Integration Guide**: Comprehensive documentation for shared-memory decoding
  - Complete field mapping for training variables (velocity, RPM, steering angle, throttle, brake, gear, lap progress)
  - Recommended `ctypes` structure declarations for Physics and Graphics pages
  - Helper functions for decoding C wide char arrays and time conversion
  - Detailed parsing instructions for telemetry dashboard variables
  - Lap progress calculation methods using `distanceTraveled` and `iCurrentTime`
  - CSV column recommendations for training and dashboard
  - Event detection snippets for lap completion
  - Diagnostic tools for structure validation
  - Common pitfalls and troubleshooting guide
  - Pre-training data collection checklist
- **AssettoCorsaGym Integration Roadmap**: Detailed roadmap for autonomous driving AI training
  - Distributed training architecture across Windows and Linux machines
  - Multi-instance setup for parallel training acceleration
  - Behavior Cloning to Reinforcement Learning pipeline (BC → RL)
  - Data collection strategy for telemetry-only training (no images)
  - Technical implementation with modular project structure
  - Hardware requirements and performance optimization guidelines
- **Test Script Enhancement**: Complete translation of telemetry collection script to English
  - English comments and variable names for better code readability
  - Standardized CSV column headers in English
  - Improved error messages and user feedback
- **GitHub Issue Templates**: Professional templates aligned with AI training objectives
  - Feature request template for AI training, telemetry analysis, and distributed computing features
  - Real usage example template for sharing training results and distributed setup experiences
  - Bug report template for technical issues specific to the project scope
- **Comprehensive Documentation Structure**: Separate telemetry guide as technical reference
  - Printable mini-guide for shared memory decoding
  - Integration examples with AI training workflows
  - Resource links and implementation guidelines

### Changed

- **Enhanced ROADMAP.md**: Complete restructure with AssettoCorsaGym integration focus
  - Removed generic Streamlit content, focused on AI training objectives
  - Added comprehensive technical documentation for autonomous driving development
  - Included distributed training setup and multi-instance configuration
  - Added hardware requirements and development considerations
  - Reorganized development phases to reflect AI training pipeline
- **Updated project structure**: Aligned with AI training and distributed computing requirements
- **Complete project reorientation**: Transitioned from generic F1 dashboard to specialized AI training platform

### Fixed

- **Structure alignment issues**: Corrected ctypes declarations for reliable shared memory reading
- **String encoding**: Proper UTF-16 handling for Assetto Corsa wide character strings

### Removed

- **Legacy Streamlit components**: Removed references to generic dashboard functionality
- **Outdated dependencies**: Cleaned up non-AI training related model references (XGBoost, TCN, YOLOv8 in generic context)
- **Incompatible roadmap items**: Removed phases not aligned with autonomous driving objectives

[Unreleased]: https://github.com/VforVitorio/F1_AC_Digital_Twin/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/VforVitorio/F1_AC_Digital_Twin/releases/tag/v1.0.0
