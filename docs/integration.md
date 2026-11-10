# R2 Gripper Visual Correction Integration

## Camera Job

The camera has one job: align the R2 gripper center to the requested
weapon-head target.

It must not decide the whole grabbing sequence. It reports:

- which slot or single target is being tracked,
- whether the target is visible,
- pixel error from the gripper grab center,
- whether the target is stable enough to grab.

The state machine owns motion and grabbing. `locked` only means visual
alignment is stable; the robot must still verify mechanical readiness
before closing the gripper.

## Recommended Mount

Use the USB wide-angle camera as the main sensor and run the model on
Jetson.

Mount it:

- near or above the R2 gripper,
- looking at the shared head rack or one test weapon head,
- slightly downward,
- with the target near the gripper grab center during final approach.

Wide-angle lenses are useful for search, but their edges distort center
measurements. During final correction, keep the target in the center half
of the image and use calibration or a center ROI.

## Gripper Center Calibration

Run:

```bash
python3 tools/pick_grab_center.py --camera 0
```

Click the true mechanical grab point in the camera image. Put the printed
values into `configs/head_rack_align.yaml`:

```yaml
grab_center_x: 320
grab_center_y: 240
alignment_axes: x
```

If the camera is remounted, this must be repeated.

## State Machine Flow

1. R2 navigates to the known head-rack approach pose using odometry,
   mechanical guides, or coarse positioning.
2. The state machine starts vision with a target slot:
   - slot 1 or 6 for spear,
   - slot 2 or 5 for fist,
   - slot 3 or 4 for palm.
3. Vision emits JSON lines.
4. In v1, read `control_code` for small left/right correction.
5. If `control_code == -2`, do not grab; search or return to the approach pose.
6. If `control_code == -1`, nudge left.
7. If `control_code == 0`, hold or wait.
8. If `control_code == 1`, nudge right.
9. If `control_code == 2`, stop correction and enter mechanical verification
   before closing the gripper.

## Control Meaning

- `dx_px > 0`: target is right of the gripper grab center.
- `dx_px < 0`: target is left of the gripper grab center.
- `dy_px > 0`: target is lower than the gripper grab center.
- `dy_px < 0`: target is higher than the gripper grab center.

Recommended integer command field:

- `control_code == -2`: no reliable target; stop correction or search.
- `control_code == -1`: nudge left.
- `control_code == 0`: hold.
- `control_code == 1`: nudge right.
- `control_code == 2`: vision locked; stop and verify mechanics before grab.

First tuning values:

- `alignment_axes`: `x` for the first robot version.
- `align_threshold_px`: `18` for 640x480 or `24` for 960x720.
- `lock_frames`: `5`.
- `lost_frames`: `6`.
- `min_detections`: `3` in slot mode, `1` effective target in single mode.

For first robot tests, only close the loop on `dx_px`. Keep height and
forward distance handled by mechanical limit, known approach pose, or a
separate slow step.

## Single-Target Debug Mode

Before the full rack is ready, use one spear/fist/palm target to validate
the gripper correction sign:

```bash
python3 -m head_rack_align.app \
  --model models/head_rack.pt \
  --camera 0 \
  --target-mode single \
  --target-slot 1 \
  --alignment-axes x \
  --show
```

Move the target to the right of the gripper center and verify `dx_px > 0`.
Move it left and verify `dx_px < 0`.

## Full Slot Mode

Use slot mode when the full rack can be photographed with several heads:

```bash
python3 -m head_rack_align.app \
  --model models/head_rack.pt \
  --camera 0 \
  --target-mode slot \
  --target-slot 1 \
  --alignment-axes x \
  --device 0 \
  --config configs/head_rack_align.yaml
```

If slot order is reversed because the camera sees the rack from the
opposite side, add:

```bash
--reverse-axis
```

## YOLO Dataset

Label three classes:

- `spear`
- `fist`
- `palm`

White prototype heads and gray competition heads may differ enough to
hurt the detector. Train with shape-focused augmentation and collect gray
competition samples as soon as possible.

Collect at least:

- 200 images from the expected approach distance,
- 100 images slightly left/right of the gripper center,
- 100 images at different exposure and light,
- 50 images with partial occlusion from the R2 gripper,
- 50 negative/background images near the rack.

Use ordinary bbox first. OBB is optional; gripper correction only needs
target center points and confidence.

## Calibration

Because the camera is wide-angle, do one of these before serious testing:

1. Preferred: calibrate with a chessboard and pass `--calibration`.
2. Faster: set a center `roi` in `configs/head_rack_align.yaml` and keep the
   target in that ROI during final alignment.

Do not trust fine pixel correction near the image edge.

