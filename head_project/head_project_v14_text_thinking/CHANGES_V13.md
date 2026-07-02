# Changes in v13

- Added asymmetric tilt motion limits. Decreasing tilt angle (physical downward motion) now uses a lower speed and acceleration.
- Added servo target deadband and minimum PWM command-change filtering to reduce buzzing and small corrective movements.
- Reduced general head speed/acceleration for a heavier mechanism.
- Moving gestures now center the head before starting: NOD, SUNGLASSES_NOD, SIGMA_NOD, SHAKE, LOOK_AROUND, CELEBRATE, DANCE, GREET and DAISY_DANCE.
- CELEBRATE and DAISY_DANCE arm motion starts after the center pose is reached.
- User tilt limits remain unchanged at 75 to 120 degrees.
