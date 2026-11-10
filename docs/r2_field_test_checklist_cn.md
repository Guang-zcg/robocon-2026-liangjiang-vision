# R2 夹爪视觉赛场试车清单

## 0. 今天目标

今天不要以重新训练为目标，先验证当前 v1 能不能上车使用：

```text
摄像头能看到目标
control_code 左右方向正确
底盘按 control_code 修正方向正确
locked 后不会提前夹
失败时能留下日志/样本
```

## 1. Jetson 视觉单独运行

先不让底盘动，只跑视觉，保存日志。

```bash
cd /home/jetson/syf/vision_code
mkdir -p logs
CAMERA=0 DEVICE=cpu SHOW=0 JSON_OUT=logs/field_quick.jsonl ./tools/run_r2_gripper_v5_jetson.sh
```

如果摄像头不是 `/dev/video0`，改成：

```bash
CAMERA=1 DEVICE=cpu SHOW=0 JSON_OUT=logs/field_quick.jsonl ./tools/run_r2_gripper_v5_jetson.sh
```

观察 JSON：

```text
目标消失: control_code = -2
目标偏左: control_code = -1
目标居中: control_code = 0 或 2
目标偏右: control_code = 1
```

## 2. 不闭合夹爪的底盘联调

状态机读取视觉 JSON，但先禁止夹爪闭合。

检查：

```text
control_code = -1 时，R2 是否向左小步修正
control_code = 1 时，R2 是否向右小步修正
control_code = 0 时，R2 是否保持或慢停
control_code = -2 时，R2 是否停止/搜索，并禁止夹取
```

如果越修越偏，说明底盘方向反了，应该在状态机里反向映射。

## 3. locked 安全确认

看到 `control_code = 2` 后，不要立刻夹。

建议状态机流程：

```text
control_code = 2
停止底盘/机构微调
停稳后继续读 3 到 5 帧
仍然 control_code = 2
确认高度/前后距离/任务状态都正确
再允许夹爪闭合
```

## 4. 真实夹取测试

只有前面三步都通过后，再做低速真实夹取。

每次夹取后记录：

```text
是否识别稳定
locked 时 dx_px 大概多少
是否夹准
是否夹偏左/右
是否误夹或提前夹
```

## 5. 失败样本必须记录

只要出现下面情况，就保存日志，并尽量拍照/录屏：

```text
有目标却 search/lost
没目标却识别出目标
目标在中心但 control_code 不是 0/2
目标左偏/右偏方向反了
locked 但实际没对准
掌/拳/矛遮挡导致识别失败
灰色端头或赛场光照导致置信度变低
```

这些失败样本后续用于 v6 模型或参数调整。

## 6. 今天通过标准

最低通过标准：

```text
目标左偏 -> control_code = -1
目标右偏 -> control_code = 1
目标居中 -> control_code = 0 或 2
目标消失 -> control_code = -2
底盘按 control_code 修正方向正确
locked 后停稳再夹，不提前夹
```

如果这些都过，R2 夹爪视觉 v1 可以认为具备上车联调价值。
