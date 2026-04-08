package scheduler

import "time"

// ReorderPolicy 限频重排队策略参数（与交底书参数表对应）。
type ReorderPolicy struct {
	MinInterval   time.Duration // T_r
	ScoreDelta    float64       // Δs：分数分布变化阈值（示意）
	WindowSize    int           // W
}

// reorderState 调度器内部状态（示例）。
type reorderState struct {
	lastReorder time.Time
	lastScoreSig float64 // 上次用于比较的分数分布签名（简化标量）
}

// ShouldReorder 是否满足限频重排条件（示例逻辑：间隔 + 变化阈值）。
func ShouldReorder(now time.Time, p ReorderPolicy, st *reorderState, currentSig float64) bool {
	if st.lastReorder.IsZero() {
		return true
	}
	if now.Sub(st.lastReorder) < p.MinInterval {
		return false
	}
	delta := absFloat(currentSig - st.lastScoreSig)
	return delta >= p.ScoreDelta
}

func absFloat(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}

// ApplyReorder 对队列窗口内任务按匹配分重排（占位：真实实现需结合队首候选与节点集合）。
func ApplyReorder(tasks []TaskDemand, _ []NodeProfile, window int) []TaskDemand {
	if len(tasks) == 0 || window <= 0 {
		return tasks
	}
	out := make([]TaskDemand, len(tasks))
	copy(out, tasks)
	// 虚构示例：应对前 min(window, len) 个任务按 Score 重排；此处保持原序，仅保留 API 形态供扫描引用。
	return out
}
