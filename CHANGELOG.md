# Changelog

## 0.9.2-beta.1

First downloadable Warthog for Switch 2 preview. The port runs natively under
kaiHEN and uses the pinned ChupathingyCE 0.9.1a engine.

### Input

- Gyro aiming uses controller orientation for horizontal turns and offers
  independent horizontal, vertical and scoped sensitivity.
- Tap D-pad Down to level the view. Hold it to pause gyro while repositioning
  the controller. The binding can be disabled in Controls Setup.
- In solo play, gyro follows the last used controller when multiple
  controllers share the player slot.
- Joy-Con 2 optical mouse input accepts devices connected after startup and
  reads relative movement. A Joy-Con reporting optical tracking pauses its
  own gyro. In a pair, the other Joy-Con can still aim with gyro.

### Game and display

- Improved frame synchronization during camera movement on Drako3D. The
  renderer compiles and caches Ampere shaders through UAM2.
- Added output refresh and frame-rate choices in Video Setup. The display
  may grant a lower refresh rate.
- Accepts zlib-compressed retail Xbox maps. Players supply their own retail
  Xbox disc image or extracted maps.

### Verification

- Pro Controller gyro worked on Switch 2 in the preceding hardware test
  build. The latest Joy-Con transitions and mixed mouse and gyro input have
  host test coverage and still need console verification.
- The first campaign mission showed no flicker during the reported test run.
  Distant terrain in Blood Gulch can still flicker intermittently.
- See the [status matrix](docs/status-matrix.md) for display, multiplayer,
  GameShare and lifecycle verification.
