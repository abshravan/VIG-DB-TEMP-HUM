import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import ReactEChartsCore from "echarts-for-react/esm/core";
import type { HistoryPoint } from "../types/api";

// Register only what's used (not the full echarts bundle) — this app targets a
// resource-constrained Raspberry Pi, so a smaller JS payload for the frontend matters too.
echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

interface Props {
  points: HistoryPoint[];
  unit: string | null;
}

const QUALITY_COLOR: Record<string, string> = {
  GOOD: "#38bdf8",
  BAD: "#f87171",
  STALE: "#facc15",
};

export function HistoryChart({ points, unit }: Props) {
  const option = {
    backgroundColor: "transparent",
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: "time",
      axisLabel: { color: "#94a3b8" },
      axisLine: { lineStyle: { color: "#334155" } },
    },
    yAxis: {
      type: "value",
      name: unit ?? undefined,
      axisLabel: { color: "#94a3b8" },
      splitLine: { lineStyle: { color: "#1e293b" } },
    },
    tooltip: {
      trigger: "axis",
      formatter: (params: { data: [string, number] }[]) => {
        const [p] = params;
        const [ts, value] = p.data;
        return `${new Date(ts).toLocaleString()}<br/>${value}${unit ?? ""}`;
      },
    },
    series: [
      {
        type: "line",
        showSymbol: points.length < 200,
        symbolSize: 5,
        lineStyle: { color: "#38bdf8", width: 1.5 },
        itemStyle: {
          color: (params: { dataIndex: number }) => QUALITY_COLOR[points[params.dataIndex]?.quality ?? "GOOD"],
        },
        data: points.map((p) => [p.timestamp, p.value]),
      },
    ],
  };

  return <ReactEChartsCore echarts={echarts} option={option} style={{ height: 380, width: "100%" }} notMerge />;
}
