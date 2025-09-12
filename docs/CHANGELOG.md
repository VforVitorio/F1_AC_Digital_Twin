# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased][Unreleased]

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

### Changed

- **Enhanced ROADMAP.md**: Complete restructure with AssettoCorsaGym integration focus
  - Removed generic Streamlit content, focused on AI training objectives
  - Added comprehensive technical documentation for autonomous driving development
  - Included distributed training setup and multi-instance configuration
  - Added hardware requirements and development considerations
- **Updated project structure**: Aligned with AI training and distributed computing requirements

### Fixed

- **Structure alignment issues**: Corrected ctypes declarations for reliable shared memory reading
- **String encoding**: Proper UTF-16 handling for Assetto Corsa wide character strings

[Unreleased]: https://github.com/VforVitorio/F1_AC_Digital_Twin/compare/HEAD
