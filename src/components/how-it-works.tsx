export function HowItWorks() {
  return <section className="panel" id="how"><div className="panel-head"><div><span className="eyebrow">Behavior contract</span><h2>Priority is explicit.</h2></div></div>
    <div className="priority"><b>1 / Thermal</b><span>≥85 °C pure red; release only ≤80 °C.</span><b>2 / Steam native</b><span>Steam-claimed Valve shim state from Game Mode Personalization.</span><b>3 / Download fallback</b><span>CEF/ACF session reducer + physical activity pulse when native pixels are unavailable.</span><b>4 / Boot</b><span>Steam blue breath while Steam is not running.</span><b>5 / Idle</b><span>Your SLEDGE fallback color/effect.</span></div>
    <p className="muted">Fremont POST fault colors are intentionally absent. The BC-250 cannot truthfully report those firmware states to userspace, so SLEDGE does not fake them.</p>
  </section>
}
