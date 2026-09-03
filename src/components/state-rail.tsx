import { useMachine, type SimState } from '@/stores/machine'

const states: { id: SimState; title: string; note: string }[] = [
  { id: 'boot', title: 'Boot', note: 'Steam blue breath' },
  { id: 'native', title: 'Steam native', note: 'Personalization owns output' },
  { id: 'download', title: 'Downloading', note: 'Fallback fill + short pulse' },
  { id: 'paused', title: 'Paused', note: 'Fill held, pulse off' },
  { id: 'thermal', title: 'Overheat', note: '85 °C trip / 80 °C clear' },
  { id: 'fallback', title: 'Fallback', note: 'Native unavailable · SLEDGE idle' },
]

export function StateRail() {
  const state = useMachine((s) => s.state)
  const demoRunning = useMachine((s) => s.demoRunning)
  const setState = useMachine((s) => s.setState)
  const restartDemo = useMachine((s) => s.restartDemo)
  return <div className="state-rail" role="list" aria-label="Simulation states">
    <button className={demoRunning ? 'state demo active' : 'state demo'} onClick={restartDemo}><span>Restart demo</span><small>{demoRunning ? 'Loop is running' : 'Resume automatic sequence'}</small></button>
    {states.map((s) => <button key={s.id} className={state === s.id ? 'state active' : 'state'} onClick={() => setState(s.id)}>
      <span>{s.title}</span><small>{s.note}</small>
    </button>)}
  </div>
}
