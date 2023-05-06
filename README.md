# Fractal Explorer
**Explore** all kinds of fractals (and listening to them).<br>
**Automatically generate** random fractal functions to your heart's content.<br>
**Customize everything** with the detailed user interface.<br>
And much more!

**Inspired by CodeParade's project:**
https://youtu.be/GiAj9WW1OfQ

Features
---------------
* Fractal **Hot-loading** at Runtime
  * Integrated **Random fractal function generator**
* Explore Real-Time fractal images
  * **64-bit** Precision support
  * Noise reduction (Overtime / Multi-Sample)
  * All Parameters Customizable at Runtime
* **User Interface** (ImGui) to control everything
* Fractal orbit **audio synthesizer**
  * Fadeout
  * **Multiple Sources**
  * All Parameters Customizable at Runtime
* Orbit **path visualization** (highly customizable)

Planned
---------------
* Support for Julia sets
* Orbit coloring
* Easy-to-use fractal function editor
* Audio performance improvement (multi-processing?)
* Improve stability (better handling of arithmetic and render errors)
* Improving fractal function generator

Notes for developers
---------------
* This project uses python.
* Mainly used libraries (does not include all libraries needed):
  * ModernGL
  * PySDL2
  * imgui-bundle (**Must be the LATEST version on GITHUB (Not on pypi yet)!!!**)
  * PyAudio
  * pygame
  * scipy
