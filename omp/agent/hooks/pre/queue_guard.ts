// omp adapter for the shared unqueued-heavy-command guard.
//
// Every compile and every test run must go through `queue` (2026-10-01: ~23
// concurrent compilers stalled the external volume to a 451 ms median file
// create vs 2 ms drained). The policy lives in ONE place -- the Python hook
// the Claude Code harness already runs -- so this file only translates omp's
// `tool_call` event into that hook's stdin JSON and its answer back into
// `{ block, reason }`. Do not re-implement the classifier here.
//
// Failure posture matches the Python hook: fails OPEN but never silently. A
// guard crash/timeout does not block the call; it is surfaced through
// `additionalContext` so the agent (and the owner) can see the guard is broken.

import { homedir } from "node:os";
import { join, resolve } from "node:path";

const GUARD = join(
  homedir(),
  "dotfiles/maintained_global_claude/hooks/unqueued_heavy_guard.py",
);
const GUARD_TIMEOUT_MS = 15_000;

type ToolCallEvent = { toolName: string; input: Record<string, unknown> };
type Ctx = { cwd: string };
type Pi = {
  on(
    event: "tool_call",
    handler: (
      event: ToolCallEvent,
      ctx: Ctx,
    ) => Promise<
      { block: true; reason: string } | { additionalContext: string } | undefined
    >,
  ): void;
};

function guardFailure(detail: string): { additionalContext: string } {
  return {
    additionalContext:
      `queue_guard hook FAILED OPEN (${detail}). The command was not checked against the ` +
      `queue rule: every compile and every test run must go through ` +
      `\`queue 'cd <wt> && cargo ...'\`. Tell the owner the guard at ${GUARD} is broken.`,
  };
}

export default function queueGuard(pi: Pi): void {
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash") return;
    const command = String(event.input.command ?? "");
    if (!command) return;

    const cwdInput = event.input.cwd;
    const cwd =
      typeof cwdInput === "string" && cwdInput
        ? resolve(ctx.cwd, cwdInput)
        : ctx.cwd;
    const payload = JSON.stringify({
      tool_name: "Bash",
      tool_input: { command },
      cwd,
    });

    let stdout: string;
    let stderr: string;
    let exitCode: number;
    try {
      const proc = Bun.spawn([GUARD], {
        stdin: new TextEncoder().encode(payload),
        stdout: "pipe",
        stderr: "pipe",
        timeout: GUARD_TIMEOUT_MS,
      });
      [stdout, stderr, exitCode] = await Promise.all([
        new Response(proc.stdout).text(),
        new Response(proc.stderr).text(),
        proc.exited,
      ]);
    } catch (err) {
      return guardFailure(`could not run guard: ${String(err)}`);
    }

    if (exitCode !== 0) {
      return guardFailure(`exit ${exitCode}: ${stderr.trim().slice(0, 300)}`);
    }
    if (!stdout.trim()) return; // guard printed nothing: allow

    let decision: { permissionDecision?: string; permissionDecisionReason?: string };
    try {
      decision = JSON.parse(stdout).hookSpecificOutput ?? {};
    } catch (err) {
      return guardFailure(`unparseable guard output: ${String(err)}`);
    }
    if (decision.permissionDecision === "deny") {
      return {
        block: true,
        reason: decision.permissionDecisionReason ?? "denied by queue_guard",
      };
    }
  });
}
