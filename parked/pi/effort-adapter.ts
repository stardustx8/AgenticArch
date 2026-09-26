/** Thin Pi boundary adapter. Bind observe/decide to the trusted local coordinator.
 * Tested against structural fakes, not an installed Pi/provider session.
 */
export interface PiSurface {
  setThinkingLevel(level: string): void;
  getThinkingLevel(): string;
  appendEntry(kind: string, data: unknown): void;
  on(event: "turn_start", handler: (event: unknown, ctx: PiContext) => Promise<void>): void;
}
export interface PiContext {
  model?: { id: string };
  signal?: AbortSignal;
  abort(): void;
}
export interface Binding {
  session: string;
  model: string;
  epoch: number;
  generation: number;
  allowed: readonly string[];
  qualified: boolean;
}
export interface Decision extends Binding {
  effort: string;
  decisionId: string;
}
export function applyEffort(pi: PiSurface, ctx: PiContext, current: Binding, d: Decision): void {
  try {
    if (!current.qualified || ctx.signal?.aborted || !d.decisionId ||
        ctx.model?.id !== current.model || d.model !== current.model ||
        d.session !== current.session || d.epoch !== current.epoch ||
        d.generation !== current.generation || !current.allowed.includes(d.effort)) {
      throw new Error("Unqualified, cancelled or stale effort decision");
    }
    pi.setThinkingLevel(d.effort);
    if (pi.getThinkingLevel() !== d.effort || ctx.model?.id !== current.model || ctx.signal?.aborted) {
      throw new Error("Requested effort was clamped, cancelled or applied to another model");
    }
    pi.appendEntry("agenticarch.effort.applied", {
      decisionId: d.decisionId, session: d.session, model: d.model,
      epoch: d.epoch, generation: d.generation, effort: d.effort,
    });
  } catch (error) {
    ctx.abort(); // Throwing alone is insufficient in permissive extension hosts.
    throw error;
  }
}
export function registerEffortHook(
  pi: PiSurface,
  observe: (ctx: PiContext) => Binding,
  decide: (binding: Binding, signal?: AbortSignal) => Promise<Decision>,
): void {
  pi.on("turn_start", async (_event, ctx) => {
    try {
      const before = observe(ctx);
      if (!before.qualified) throw new Error("Local integration is not qualified");
      const d = await decide(before, ctx.signal); // Provider-free local sidecar, with its own timeout.
      applyEffort(pi, ctx, observe(ctx), d); // Re-observe after awaiting; never use stale settings.
    } catch (error) {
      ctx.abort();
      throw error;
    }
  });
}
