package scheduler

import "time"

// HeartbeatConfig 节点心跳契约参数（从属特征 P3）。
type HeartbeatConfig struct {
	Interval    time.Duration
	DeadAfter   time.Duration // 超过该时间未收到心跳则判定假死
}

// NodeHeartbeat 最近一次心跳时间（示例结构）。
type NodeHeartbeat struct {
	NodeID   string
	LastSeen time.Time
}

// IsProbablyDead 判定节点是否假死（示意）。
func IsProbablyDead(h NodeHeartbeat, now time.Time, cfg HeartbeatConfig) bool {
	return now.Sub(h.LastSeen) > cfg.DeadAfter
}
