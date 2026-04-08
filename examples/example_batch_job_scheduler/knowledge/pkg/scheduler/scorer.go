package scheduler

import "math"

// Score 根据需求向量与节点画像计算匹配分（简化线性加权 + 过载惩罚，示例实现）。
func Score(d TaskDemand, p NodeProfile) float64 {
	if p.CPUAvail <= 0 || p.MemFreeMB <= 0 {
		return -1
	}
	cpuFit := d.CPUBudget * p.CPUAvail
	memFit := math.Min(1.0, p.MemFreeMB/math.Max(1, d.MemPeakMB))
	ioFit := (1.0 - p.IOBusy) * d.IOSensitive
	inflightPenalty := float64(p.Inflight) * 0.05
	return cpuFit + memFit + ioFit - inflightPenalty
}
