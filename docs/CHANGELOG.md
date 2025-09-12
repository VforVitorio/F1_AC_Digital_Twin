# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased][Unreleased]

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
