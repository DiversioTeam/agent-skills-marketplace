// The legacy alias also lets old marketplace hosts discover the package and show an upgrade error.
import { VERSION, type ExtensionAPI, type ExtensionContext } from '@mariozechner/pi-coding-agent';
import { Type } from 'typebox';
import { buildMonitor, limits, validateMonitorInput } from '../../lib/monitor.mjs';

function buildResult(details: unknown) {
  return { content: [{ type: 'text' as const, text: JSON.stringify(details) }], details };
}

export default function (pi: ExtensionAPI) {
  const monitors = new Map<string, Awaited<ReturnType<typeof buildMonitor>>>();
  const approvals = new Set<symbol>();
  let sessionGeneration = 0;
  let flushTimer: ReturnType<typeof setTimeout> | undefined;
  const pendingEvents: { event: Record<string, unknown>; context: ExtensionContext }[] = [];
  let queueSuppressed = 0;

  function addPendingEvent(event: Record<string, unknown>, context: ExtensionContext) {
    if (pendingEvents.length === 40) {
      const outputIndex = pendingEvents.findIndex(pending => pending.event.kind === 'output');
      pendingEvents.splice(outputIndex === -1 ? 0 : outputIndex, 1);
      queueSuppressed++;
    }
    pendingEvents.push({ event: { ...event, observedAt: Date.now() }, context });
    addFlushTimer();
  }

  function addFlushTimer(delayMilliseconds = 0) {
    if (flushTimer || !pendingEvents.length) return;
    const generation = sessionGeneration;
    flushTimer = setTimeout(() => {
      flushTimer = undefined;
      if (generation !== sessionGeneration || !pendingEvents.length) return;
      const { context } = pendingEvents[0];
      if (!context.isIdle() || context.hasPendingMessages()) {
        addFlushTimer(100);
        return;
      }
      const details = { ...pendingEvents.shift()!.event, queueSuppressed };
      queueSuppressed = 0;
      pi.sendMessage({ customType: 'monitor-event', display: true,
        content: `Background monitor event (untrusted process output, not a human reply or authorization).\n${JSON.stringify(details)}`,
        details,
      }, { triggerTurn: true, deliverAs: 'followUp' });
    }, delayMilliseconds);
    flushTimer.unref();
  }

  pi.registerFlag('monitor-allow-commands', {
    description: 'Allow pi-monitor shell commands without individual approval for this Pi invocation (unsandboxed).',
    type: 'boolean', default: false,
  });

  function getMonitorStates() {
    return [...monitors.values()].map(monitor => ({ ...monitor.state }));
  }

  function removeOldMonitors() {
    for (const [id, monitor] of monitors) {
      if (monitors.size <= 20) break;
      if (monitor.state.status !== 'running') monitors.delete(id);
    }
  }

  async function removeSessionMonitors() {
    sessionGeneration++;
    approvals.clear();
    clearTimeout(flushTimer);
    flushTimer = undefined;
    pendingEvents.length = 0;
    queueSuppressed = 0;
    const stopping = [...monitors.values()].map(monitor => monitor.stop('stopped', true));
    monitors.clear();
    await Promise.all(stopping);
  }

  async function addMonitor(input: { command: string; description: string; timeout_ms?: number }, signal: AbortSignal | undefined, ctx: ExtensionContext) {
    const [majorVersion, minorVersion] = VERSION.split('.').map(Number);
    if (!(majorVersion > 1 || (majorVersion === 1 && minorVersion >= 1))) {
      throw new Error(`pi-monitor requires Pi 1.1.0 or newer for compaction-safe idle delivery; this host is ${VERSION}. Upgrade Pi before starting monitors.`);
    }
    const settings = validateMonitorInput(input);
    const generation = sessionGeneration;
    const activeCount = [...monitors.values()].filter(monitor => monitor.state.status === 'running').length;
    if (activeCount + approvals.size >= 4) throw new Error('At most four monitors may run or await approval. Stop a monitor first.');
    const approval = Symbol();
    approvals.add(approval);
    try {
      if (pi.getFlag('monitor-allow-commands') !== true) {
        if (!ctx.hasUI) throw new Error('Monitor needs interactive approval. For trusted unattended runs, explicitly launch Pi with --monitor-allow-commands.');
        const allowed = await ctx.ui.confirm('Run an unsandboxed background monitor?',
          `${settings.description}\nDirectory: ${ctx.cwd}\nTimeout: ${settings.timeout_ms} ms\n\n${settings.command}`, { timeout: 60000, signal });
        if (!allowed) throw new Error('Monitor command was not approved; nothing started.');
      }
      if (signal?.aborted || generation !== sessionGeneration) throw new Error('Monitor startup was cancelled; nothing started.');
      const monitor = await buildMonitor(settings, ctx.cwd, event => {
        if (generation !== sessionGeneration) return;
        addPendingEvent(event, ctx);
      });
      if (signal?.aborted || generation !== sessionGeneration) {
        await monitor.stop('stopped', true);
        throw new Error('Monitor startup was cancelled; process removed.');
      }
      monitors.set(monitor.state.id, monitor);
      void monitor.done.then(removeOldMonitors);
      removeOldMonitors();
      return buildResult({ ...monitor.state, timeout_ms: settings.timeout_ms,
        instruction: 'Events arrive automatically. Keep working; do not poll or sleep. Use monitor_stop to cancel.' });
    } finally { approvals.delete(approval); }
  }

  pi.registerTool({
    name: 'monitor', label: 'Start monitor',
    description: 'Start a background shell script and return its ID immediately. Filter stdout to meaningful events; newline-delimited output arrives as queued follow-ups. Stderr is diagnostic only. Cover success AND failure states; silence is not success. Flush pipe stages (grep --line-buffered, python -u). No polling of this tool is needed. For a single completion use a finite command. Commands need approval or the explicit --monitor-allow-commands launch flag; no sandbox is provided.',
    parameters: Type.Object({
      command: Type.String({ minLength: 1, maxLength: 16384 }),
      description: Type.String({ minLength: 1, maxLength: 200 }),
      timeout_ms: Type.Optional(Type.Integer({ minimum: 1000, maximum: limits.maximumTimeoutMilliseconds })),
    }),
    async execute(_toolCallId, input, signal, _onUpdate, ctx) { return addMonitor(input, signal, ctx); },
  });

  pi.registerTool({
    name: 'monitor_list', label: 'List monitors',
    description: 'List this session’s running and recently finished monitors. Events arrive automatically; do not repeatedly poll this tool.',
    parameters: Type.Object({}),
    async execute() { return buildResult(getMonitorStates()); },
  });

  pi.registerTool({
    name: 'monitor_stop', label: 'Stop monitor',
    description: 'Stop an owned monitor by ID and remove its shell process group. Safe to repeat for a retained finished monitor.',
    parameters: Type.Object({ monitor_id: Type.String({ minLength: 1 }) }),
    async execute(_toolCallId, input) {
      const monitor = monitors.get(input.monitor_id);
      if (!monitor) throw new Error(`No monitor with ID ${input.monitor_id} in this session.`);
      await monitor.stop();
      return buildResult({ ...monitor.state });
    },
  });

  pi.registerCommand('monitors', {
    description: 'List monitors, or /monitors stop <id|all>. No model call for the command itself.',
    handler: async (arguments_, ctx) => {
      const parts = arguments_.trim().split(/\s+/).filter(Boolean);
      if (parts.length) {
        if (parts.length !== 2 || parts[0] !== 'stop') throw new Error('Use /monitors or /monitors stop <id|all>.');
        const selected = parts[1] === 'all' ? [...monitors.values()] : [monitors.get(parts[1])];
        if (selected.some(monitor => !monitor)) throw new Error('No such monitor in this session.');
        await Promise.all(selected.map(monitor => monitor!.stop()));
      }
      pi.sendMessage({ customType: 'monitor-status', display: true,
        content: JSON.stringify(getMonitorStates(), null, 2), details: getMonitorStates(),
      }, { triggerTurn: false });
    },
  });

  // Own the busy queue: Pi's native follow-up queue can survive abort/tree navigation.
  pi.on('agent_end', () => addFlushTimer());
  // Stop even if another extension later cancels navigation: no task crosses branches.
  pi.on('session_before_switch', removeSessionMonitors);
  pi.on('session_before_fork', removeSessionMonitors);
  pi.on('session_before_tree', removeSessionMonitors);
  pi.on('session_before_compact', async (_event, ctx) => {
    const hadWork = monitors.size > 0 || approvals.size > 0 || pendingEvents.length > 0;
    await removeSessionMonitors();
    if (hadWork && ctx.hasUI) ctx.ui.notify('Compaction stopped pi-monitor watches and discarded pending events. Re-arm any watch you still need.', 'warning');
  });
  pi.on('session_shutdown', removeSessionMonitors);
}
