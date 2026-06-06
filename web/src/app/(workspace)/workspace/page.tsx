import { ModuleCard } from "@/components/ui/module-card";
import { primaryNavigation } from "@/lib/navigation";
import { workflowStages } from "@/lib/workflow";

export default function WorkspacePage() {
  return (
    <main>
      <section className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
        <p className="text-sm font-medium text-blue-700">今日工作台</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">机构自查闭环总览</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          当前阶段先提供前端基座和模块入口。后续计划会把项目、材料、疑点、补证和报告逐步接入真实 API。
        </p>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        {primaryNavigation.slice(1).map((item) => (
          <ModuleCard
            key={item.href}
            title={item.label}
            description={item.description}
            href={item.href}
            badge={item.emphasis === "primary" ? "核心流程" : "流程模块"}
          />
        ))}
      </section>

      <section className="mt-6 rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
        <h2 className="text-lg font-semibold text-slate-950">AI 自查状态机</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {workflowStages.map((stage) => (
            <div key={stage.stage} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm font-semibold text-slate-950">{stage.label}</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">{stage.description}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
