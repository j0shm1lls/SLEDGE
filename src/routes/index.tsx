import { useEffect } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { Chassis } from '@/components/chassis'
import { ControlPanel } from '@/components/control-panel'
import { DiagnosticsPanel } from '@/components/diagnostics-panel'
import { HowItWorks } from '@/components/how-it-works'
import { InstallPanel } from '@/components/install-panel'
import { NativePathPanel } from '@/components/native-path-panel'
import { StateRail } from '@/components/state-rail'
import { demoFrameAt } from '@/lib/demo'
import { useMachine } from '@/stores/machine'

export const Route = createFileRoute('/')({ component: Home })

function Home() {
  const demoRunning = useMachine((s) => s.demoRunning)
  const demoEpoch = useMachine((s) => s.demoEpoch)
  const applyDemoFrame = useMachine((s) => s.applyDemoFrame)

  useEffect(() => {
    if (!demoRunning) return
    const started = performance.now()
    let raf = 0
    const tick = () => {
      const frame = demoFrameAt((performance.now() - started) / 1000)
      applyDemoFrame(frame.state, frame.progress)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [demoRunning, demoEpoch, applyDemoFrame])

  return <main>
    <header className="nav"><a className="brand" href="#top">NEXBAR<span>2</span></a><nav><a href="#native">Native path</a><a href="#customize">Control</a><a href="#diagnostics">Diagnostics</a><a href="#install">Install</a></nav></header>
    <section className="hero" id="top"><div className="hero-copy"><span className="eyebrow">Redux × SteamOS × Nollie1</span><h1>Make the front bar feel <em>native.</em></h1><p>Steam’s own Game Mode controls when they’re available. A deterministic fallback when they aren’t. One 24-pixel bar, one source of truth.</p><div className="hero-actions"><a className="primary" href="/nexbar/nexbar.zip">Get the package</a><a className="ghost" href="#native">See the signal path</a></div></div><div className="hero-meta"><code>STEAMOS / 17 LOGICAL</code><code>REDUX / 24 PHYSICAL</code><code>NOLLIE1 / CDC PRIMARY</code></div></section>
    <Chassis />
    <div className="layout"><aside><span className="eyebrow">Simulate</span><StateRail /></aside><div className="stack"><NativePathPanel /><ControlPanel /><DiagnosticsPanel /><HowItWorks /><InstallPanel /></div></div>
    <footer><span>NexBar2</span><span>Built for the BC-250 Redux configuration.</span></footer>
  </main>
}
