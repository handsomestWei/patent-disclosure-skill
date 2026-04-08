// Package scheduler 虚构示例：批任务调度领域类型定义（教学用，非生产代码）。
package scheduler

import "time"

// TaskDemand 任务需求向量（示意字段，可随业务扩展）。
type TaskDemand struct {
	ID           string
	CPUBudget    float64 // 相对 CPU 需求权重
	MemPeakMB    float64
	IOSensitive  float64 // IO 敏感度 0~1
	MaxWait      time.Duration
	Priority     int // 业务静态优先级
}

// NodeProfile 节点多维资源画像（示意）。
type NodeProfile struct {
	NodeID      string
	CPUAvail    float64 // 可用比例 0~1
	MemFreeMB   float64
	IOBusy      float64 // IO 饱和度 0~1
	Inflight    int     // 在途任务数
	UpdatedAt   time.Time
}

// MatchScore 任务在某节点上的匹配分（越大越适合）。
type MatchScore struct {
	TaskID  string
	NodeID  string
	Score   float64
}
