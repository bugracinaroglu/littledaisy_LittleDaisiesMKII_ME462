# Dance and Greeting Guide

## DANCE

Purpose: a smooth sunglasses dance.

Sequence for one count:

```text
right/up -> centre/down -> left/up -> centre/down
```

Call:

```python
robot_head.dance(count=3, hold_ms=7000)
```

Manual key: `6`

Serial:

```text
GESTURE:DANCE,3,7000
```

## GREET

Purpose: greet people on both sides.

Sequence:

```text
turn right -> nod count times -> turn left -> nod count times -> centre
```

Call:

```python
robot_head.greet(nod_count=3, hold_ms=7000)
```

Manual key: `7`

Serial:

```text
GESTURE:GREET,3,7000
```

## DAISY_DANCE

Purpose: a more characteristic full-body Papatya dance.

It uses the same head path as `DANCE` and adds alternating two-arm movement.

Call:

```python
robot_head.daisy_dance(count=3, hold_ms=8000)
```

Manual key: `8`

Serial:

```text
GESTURE:DAISY_DANCE,3,8000
```

## Safety and tuning

All angles are clamped by the existing servo limits. Tune only the constants in
`microcontrollerside/config.py`. Test with small offsets first, especially on a
new mechanical assembly.
