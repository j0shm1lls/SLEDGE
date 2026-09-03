import { i as __toESM } from "../_runtime.mjs";
import { a as require_jsx_runtime, o as require_react } from "../_libs/@radix-ui/react-collection+[...].mjs";
import { n as create, t as persist } from "../_libs/zustand.mjs";
import { i as SliderTrack, n as SliderRange, r as SliderThumb, t as Slider } from "../_libs/@radix-ui/react-slider+[...].mjs";
import { n as ToggleGroupItem, t as ToggleGroup } from "../_libs/radix-ui__react-toggle-group.mjs";
import { i as Cpu, n as RadioTower, r as Gauge, t as Usb } from "../_libs/lucide-react.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/routes-BZESBVMJ.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
var OFF = Object.freeze({
	r: 0,
	g: 0,
	b: 0
});
var STEAM_BLUE = Object.freeze({
	r: 58,
	g: 167,
	b: 255
});
var WHITE = Object.freeze({
	r: 240,
	g: 244,
	b: 255
});
var clamp = (n, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, n));
var mix = (a, b, t) => ({
	r: Math.round(a.r + (b.r - a.r) * clamp(t)),
	g: Math.round(a.g + (b.g - a.g) * clamp(t)),
	b: Math.round(a.b + (b.b - a.b) * clamp(t))
});
var scaleRgb = (c, k) => ({
	r: Math.round(clamp(c.r * k, 0, 255)),
	g: Math.round(clamp(c.g * k, 0, 255)),
	b: Math.round(clamp(c.b * k, 0, 255))
});
var hsv = (h, s, v) => {
	const hh = (h % 360 + 360) % 360;
	const c = v * s;
	const x = c * (1 - Math.abs(hh / 60 % 2 - 1));
	const m = v - c;
	let r = 0, g = 0, b = 0;
	if (hh < 60) [r, g, b] = [
		c,
		x,
		0
	];
	else if (hh < 120) [r, g, b] = [
		x,
		c,
		0
	];
	else if (hh < 180) [r, g, b] = [
		0,
		c,
		x
	];
	else if (hh < 240) [r, g, b] = [
		0,
		x,
		c
	];
	else if (hh < 300) [r, g, b] = [
		x,
		0,
		c
	];
	else [r, g, b] = [
		c,
		0,
		x
	];
	return {
		r: Math.round((r + m) * 255),
		g: Math.round((g + m) * 255),
		b: Math.round((b + m) * 255)
	};
};
function renderIdleEffect(effect, color, brightness, now, count = 17) {
	const n = Math.max(1, Math.round(count));
	const level = clamp(brightness);
	if (effect === "rainbow") return Array.from({ length: n }, (_, i) => scaleRgb(hsv(i / n * 360 + now * 72, .86, 1), level));
	if (effect === "patrol") {
		const span = Math.max(1, n - 1);
		const phase = now / 2.2 % 2;
		const pos = phase < 1 ? phase * span : (2 - phase) * span;
		return Array.from({ length: n }, (_, i) => {
			const fall = Math.max(0, 1 - Math.abs(i - pos) / 1.35);
			return fall > 0 ? scaleRgb(color, level * fall * fall) : OFF;
		});
	}
	const px = scaleRgb(color, level * (effect === "breath" ? .2 + .8 * ((Math.sin(now * Math.PI * 2 / 2.2 - Math.PI / 2) + 1) / 2) : 1));
	return Array.from({ length: n }, () => px);
}
function mapPhysical(logical, count, mode, reverse) {
	if (count <= 0) return [];
	if (!logical.length) return Array.from({ length: count }, () => OFF);
	let out;
	if (mode === "center" && count >= logical.length) {
		const left = Math.floor((count - logical.length) / 2);
		out = [
			...Array.from({ length: left }, () => OFF),
			...logical,
			...Array.from({ length: count - left - logical.length }, () => OFF)
		];
	} else if (mode === "nearest") out = Array.from({ length: count }, (_, i) => {
		return logical[count === 1 ? 0 : Math.round(i * (logical.length - 1) / (count - 1))];
	});
	else out = Array.from({ length: count }, (_, i) => {
		if (count === 1 || logical.length === 1) return logical[0];
		const pos = i * (logical.length - 1) / (count - 1);
		const lo = Math.floor(pos);
		const hi = Math.min(logical.length - 1, lo + 1);
		return mix(logical[lo], logical[hi], pos - lo);
	});
	return reverse ? [...out].reverse() : out;
}
function progressFill(progress, count, color = STEAM_BLUE) {
	const p = clamp(progress);
	const filled = p > 0 ? Math.min(count, Math.ceil(p * count - 1e-12)) : 0;
	return Array.from({ length: count }, (_, i) => i < filled ? color : OFF);
}
var pulseColor = (base) => mix(base, WHITE, .62);
var ActivityPulse = class {
	cycleStartedAt = null;
	head = -1;
	active = false;
	lastRenderAt = null;
	periodS;
	fps;
	minProgress;
	constructor(periodS = 2, fps = 40, minProgress = .1) {
		this.periodS = periodS;
		this.fps = fps;
		this.minProgress = minProgress;
	}
	reset() {
		this.cycleStartedAt = null;
		this.head = -1;
		this.active = false;
		this.lastRenderAt = null;
	}
	render(now, progress, paused, baseFrame) {
		const frame = baseFrame.map((p) => ({ ...p }));
		if (paused || progress < this.minProgress || frame.length === 0) {
			this.reset();
			return frame;
		}
		const filled = baseFrame.reduce((last, p, i) => p.r || p.g || p.b ? i + 1 : last, 0);
		if (!filled) {
			this.reset();
			return frame;
		}
		const edge = filled - 1;
		if (this.cycleStartedAt == null) {
			this.cycleStartedAt = now;
			this.head = 0;
			this.active = true;
			this.lastRenderAt = now;
		} else if (!this.active && now - this.cycleStartedAt >= this.periodS) {
			this.cycleStartedAt = now;
			this.head = 0;
			this.active = true;
			this.lastRenderAt = now;
		}
		if (!this.active || this.head > edge) return frame;
		frame[this.head] = pulseColor(frame[this.head]);
		const frameDt = 1 / this.fps;
		if (this.lastRenderAt == null || now - this.lastRenderAt + 1e-9 >= frameDt) {
			this.lastRenderAt = now;
			if (this.head >= edge) this.active = false;
			else this.head += 1;
		}
		return frame;
	}
};
var useMachine = create()(persist((set) => ({
	state: "boot",
	progress: .04,
	color: "#3aa7ff",
	brightness: 25,
	effect: "solid",
	mapping: "stretch",
	reverse: false,
	pulsePeriod: 2,
	physical: 24,
	tripC: 85,
	clearC: 80,
	demoRunning: true,
	demoEpoch: 0,
	setState: (state) => set({
		state,
		demoRunning: false
	}),
	patch: (next) => set({
		...next,
		demoRunning: false
	}),
	applyDemoFrame: (state, progress) => set((current) => current.demoRunning ? {
		state,
		progress
	} : current),
	restartDemo: () => set((current) => ({
		state: "boot",
		progress: .04,
		demoRunning: true,
		demoEpoch: current.demoEpoch + 1
	}))
}), { name: "nexbar2-preview" }));
var hex = (value) => {
	const s = value.replace("#", "");
	return {
		r: parseInt(s.slice(0, 2), 16) || 0,
		g: parseInt(s.slice(2, 4), 16) || 0,
		b: parseInt(s.slice(4, 6), 16) || 0
	};
};
var scale = (c, k) => ({
	r: Math.round(c.r * k),
	g: Math.round(c.g * k),
	b: Math.round(c.b * k)
});
var css = (c) => `rgb(${c.r} ${c.g} ${c.b})`;
function Chassis() {
	const m = useMachine();
	const [t, setT] = (0, import_react.useState)(0);
	const pulse = (0, import_react.useMemo)(() => new ActivityPulse(m.pulsePeriod, 40, .1), [m.pulsePeriod]);
	(0, import_react.useEffect)(() => {
		let raf = 0;
		const start = performance.now();
		const loop = () => {
			setT((performance.now() - start) / 1e3);
			raf = requestAnimationFrame(loop);
		};
		raf = requestAnimationFrame(loop);
		return () => cancelAnimationFrame(raf);
	}, []);
	const dim = m.brightness / 100;
	let physical;
	if (m.state === "boot") {
		const env = .2 + .8 * ((Math.sin(t * Math.PI * 2 / 2.2 - Math.PI / 2) + 1) / 2);
		physical = Array.from({ length: m.physical }, () => scale(STEAM_BLUE, env));
	} else if (m.state === "thermal") physical = Array.from({ length: m.physical }, () => ({
		r: 255,
		g: 0,
		b: 0
	}));
	else if (m.state === "download" || m.state === "paused") {
		const base = progressFill(m.progress, m.physical, scale(STEAM_BLUE, Math.max(.25, dim)));
		physical = pulse.render(t, m.progress, m.state === "paused", base);
		if (m.reverse) physical = [...physical].reverse();
	} else if (m.state === "fallback") physical = mapPhysical(renderIdleEffect(m.effect, hex(m.color), dim, t, 17), m.physical, m.mapping, m.reverse);
	else physical = mapPhysical(Array.from({ length: 17 }, () => scale(STEAM_BLUE, .42)), m.physical, m.mapping, m.reverse);
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("section", {
		className: "chassis-wrap",
		"aria-label": "Redux front-bar simulation",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "chassis",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "chassis-top",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "NEXGEN3D / REDUX" }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
						className: "indicator",
						"aria-label": "Power indicator on"
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { className: "vent-grid" }),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "bar-well",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "led-strip",
						"data-led-count": m.physical,
						style: { gridTemplateColumns: `repeat(${m.physical}, minmax(0,1fr))` },
						children: physical.map((p, i) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "led",
							style: {
								"--led": css(p),
								"--glow": p.r || p.g || p.b ? css(p) : "transparent"
							}
						}, i))
					})
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "chassis-foot",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "BC-250" }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: [
						"NOLLIE1 / ",
						m.physical,
						" PX"
					] })]
				})
			]
		})
	});
}
function Range({ value, min, max, step, onValue, label }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Slider, {
		"aria-label": label,
		className: "slider",
		value: [value],
		min,
		max,
		step,
		onValueChange: ([n]) => onValue(n),
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(SliderTrack, {
			className: "slider-track",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(SliderRange, { className: "slider-range" })
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(SliderThumb, { className: "slider-thumb" })]
	});
}
function ControlPanel() {
	const m = useMachine();
	const paused = m.state === "paused";
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
		className: "panel",
		id: "customize",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "panel-head",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "eyebrow",
					children: "Fallback & mapping"
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", { children: "Control what Steam doesn’t." })] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "badge",
					children: "LOCAL ONLY"
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
				className: "muted",
				children: [
					"When ",
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("b", { children: "Steam native" }),
					" owns the bar, ordinary color and effect choices come from Game Mode Personalization. These controls define NexBar’s fallback behavior and physical mapping."
				]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "control-grid",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
						className: "field",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "Fallback color" }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "color-row",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
								"aria-label": "Fallback color",
								type: "color",
								value: m.color,
								onChange: (e) => m.patch({ color: e.target.value })
							}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("code", { children: m.color })]
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "field",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: ["Idle brightness ", /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("b", { children: [m.brightness, "%"] })] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Range, {
							label: "Idle brightness",
							value: m.brightness,
							min: 0,
							max: 100,
							step: 1,
							onValue: (brightness) => m.patch({ brightness })
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "field full",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "Fallback effect" }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ToggleGroup, {
							"aria-label": "Fallback effect",
							type: "single",
							className: "toggles",
							value: m.effect,
							onValueChange: (effect) => effect && m.patch({ effect }),
							children: [
								"solid",
								"breath",
								"rainbow",
								"patrol"
							].map((x) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ToggleGroupItem, {
								value: x,
								children: x
							}, x))
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "field",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: ["Physical LEDs ", /* @__PURE__ */ (0, import_jsx_runtime.jsx)("b", { children: m.physical })] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Range, {
							label: "Physical LEDs",
							value: m.physical,
							min: 17,
							max: 64,
							step: 1,
							onValue: (physical) => m.patch({ physical })
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "field",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: ["Download progress ", /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("b", { children: [Math.round(m.progress * 100), "%"] })] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Range, {
							label: "Download progress",
							value: m.progress,
							min: 0,
							max: 1,
							step: .01,
							onValue: (progress) => m.patch({ progress })
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "field",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: ["Activity pulse ", /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("b", { children: [m.pulsePeriod.toFixed(1), "s"] })] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Range, {
							label: "Activity pulse period",
							value: m.pulsePeriod,
							min: .6,
							max: 8,
							step: .1,
							onValue: (pulsePeriod) => m.patch({ pulsePeriod })
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
						className: "field",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "Trip temperature" }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
							className: "number-input",
							"aria-label": "Trip temperature",
							type: "number",
							min: 40,
							max: 120,
							value: m.tripC,
							onChange: (e) => m.patch({ tripC: Number(e.target.value) })
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
						className: "field",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "Clear temperature" }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
							className: "number-input",
							"aria-label": "Clear temperature",
							type: "number",
							min: 35,
							max: 119,
							value: m.clearC,
							onChange: (e) => m.patch({ clearC: Number(e.target.value) })
						})]
					})
				]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "seg-row",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: [
					"17 → ",
					m.physical,
					" mapping"
				] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ToggleGroup, {
					"aria-label": "LED mapping",
					type: "single",
					className: "toggles",
					value: m.mapping,
					onValueChange: (mapping) => mapping && m.patch({ mapping }),
					children: [
						"stretch",
						"nearest",
						"center"
					].map((x) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ToggleGroupItem, {
						value: x,
						children: x
					}, x))
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "check-grid",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
					className: "check",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
						type: "checkbox",
						checked: m.reverse,
						onChange: (e) => m.patch({ reverse: e.target.checked })
					}), " Reverse physical orientation"]
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
					className: "check",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
						"aria-label": "Pause download",
						type: "checkbox",
						checked: paused,
						onChange: (e) => m.setState(e.target.checked ? "paused" : "download")
					}), " Pause download"]
				})]
			})
		]
	});
}
function DiagnosticsPanel() {
	const m = useMachine();
	const native = m.state === "native";
	const fallbackDownload = m.state === "download" || m.state === "paused";
	const rows = [
		["OUTPUT OWNER", m.state === "thermal" ? "thermal override" : native ? "steam-native" : fallbackDownload ? "download-fallback" : m.state === "boot" ? "boot" : "idle"],
		["SHIM", native ? "active · seq 284" : "available · awaiting Steam ownership"],
		["BACKEND", `hidraw · Nollie1 · ${m.physical} LEDs`],
		["MAPPING", `17 → ${m.physical} · ${m.mapping}${m.reverse ? " · reversed" : ""}`],
		["THERMAL", m.state === "thermal" ? `${(m.tripC + .4).toFixed(1)} °C · latched` : `67.2 °C · clear (${m.tripC}/${m.clearC})`],
		["DOWNLOAD", fallbackDownload ? `${Math.round(m.progress * 100)}% · ${m.state === "paused" ? "paused" : "active"} · CEF` : "idle"],
		["DEMO", m.demoRunning ? "running · simulated states" : "manual simulation"]
	];
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
		className: "panel",
		id: "diagnostics",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "panel-head",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "eyebrow",
					children: "Diagnostics"
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", { children: "No mystery state." })] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "badge",
					children: "SIMULATION"
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "diag",
				children: rows.map(([k, v]) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "diag-row",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("code", { children: k }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: v })]
				}, k))
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "muted",
				children: "On the real machine the daemon reports why native ownership is active or why it fell back. A shim that exists but remains at sequence 1 never claims the bar; a static Steam setting remains native as long as valid shim snapshots continue to read."
			})
		]
	});
}
function HowItWorks() {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
		className: "panel",
		id: "how",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "panel-head",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "eyebrow",
					children: "Behavior contract"
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", { children: "Priority is explicit." })] })
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "priority",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("b", { children: "1 / Thermal" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "≥85 °C pure red; release only ≤80 °C." }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("b", { children: "2 / Steam native" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "Steam-claimed Valve shim state from Game Mode Personalization." }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("b", { children: "3 / Download fallback" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "CEF/ACF session reducer + physical activity pulse when native pixels are unavailable." }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("b", { children: "4 / Boot" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "Steam blue breath while Steam is not running." }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("b", { children: "5 / Idle" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "Your NexBar fallback color/effect." })
				]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "muted",
				children: "Fremont POST fault colors are intentionally absent. The BC-250 cannot truthfully report those firmware states to userspace, so NexBar2 does not fake them."
			})
		]
	});
}
function InstallPanel() {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
		className: "panel",
		id: "install",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "panel-head",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "eyebrow",
					children: "SteamOS package"
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", { children: "Install once. Update one file." })] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("a", {
					className: "primary",
					href: "/nexbar/nexbar.zip",
					children: "Download nexbar.zip"
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "install-grid",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("b", { children: "First install" }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", { children: [
						"Run ",
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("code", { children: "install.sh" }),
						" in Desktop Mode. It installs the user service and Nollie permissions, then builds the Valve-compatible shim only when it is missing and matching headers are available."
					] })] }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("b", { children: "Normal daemon update" }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", { children: [
						"Replace ",
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("code", { children: "nexbar-bridge.py" }),
						" and restart ",
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("code", { children: "nexbar.service" }),
						". No kernel rebuild for Python-only changes."
					] })] }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("b", { children: "After a SteamOS kernel update" }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", { children: [
						"Run ",
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("code", { children: "./install.sh --repair-shim" }),
						" only if diagnostics report the Valve shim missing for the running kernel."
					] })] })
				]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("pre", { children: `journalctl --user -u nexbar -f\n# nexbar running\n# control UI http://127.0.0.1:1873/\n# hidraw /dev/hidrawX (Nollie...) leds=24` })
		]
	});
}
function NativePathPanel() {
	const steps = [
		[
			Gauge,
			"Steam Game Mode",
			"Personalization writes Valve’s 17-LED interface."
		],
		[
			Cpu,
			"valve-leds shim",
			"Captures color, brightness, effects and manual pixels."
		],
		[
			RadioTower,
			"NexBar bridge",
			"Arbitrates safety, maps 17 → 24 and renders effects."
		],
		[
			Usb,
			"Nollie1 hidraw",
			"65-byte GRB packets. OpenRGB is fallback only."
		]
	];
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
		className: "panel native-panel",
		id: "native",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "panel-head",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "eyebrow",
					children: "Preferred path"
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", { children: "Steam owns the bar." })] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "status-dot",
					children: "NATIVE FIRST"
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "lede",
				children: "NexBar2 does not invent a second color picker when Steam can provide the real one. The shim exposes the interface Game Mode expects; the bridge translates that output to your 24 physical LEDs."
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "pipeline",
				children: steps.map(([Icon, title, note], i) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "pipe-step",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Icon, { size: 20 }),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("b", { children: title }),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: note }),
						i < steps.length - 1 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("i", { children: "→" })
					]
				}, title))
			})
		]
	});
}
var states = [
	{
		id: "boot",
		title: "Boot",
		note: "Steam blue breath"
	},
	{
		id: "native",
		title: "Steam native",
		note: "Personalization owns output"
	},
	{
		id: "download",
		title: "Downloading",
		note: "Fallback fill + short pulse"
	},
	{
		id: "paused",
		title: "Paused",
		note: "Fill held, pulse off"
	},
	{
		id: "thermal",
		title: "Overheat",
		note: "85 °C trip / 80 °C clear"
	},
	{
		id: "fallback",
		title: "Fallback",
		note: "Native unavailable · NexBar idle"
	}
];
function StateRail() {
	const state = useMachine((s) => s.state);
	const demoRunning = useMachine((s) => s.demoRunning);
	const setState = useMachine((s) => s.setState);
	const restartDemo = useMachine((s) => s.restartDemo);
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "state-rail",
		role: "list",
		"aria-label": "Simulation states",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
			className: demoRunning ? "state demo active" : "state demo",
			onClick: restartDemo,
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "Restart demo" }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("small", { children: demoRunning ? "Loop is running" : "Resume automatic sequence" })]
		}), states.map((s) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
			className: state === s.id ? "state active" : "state",
			onClick: () => setState(s.id),
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: s.title }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("small", { children: s.note })]
		}, s.id))]
	});
}
var DEMO_STEPS = [
	{
		state: "boot",
		duration: 4,
		progressFrom: .04,
		progressTo: .04
	},
	{
		state: "native",
		duration: 3.2,
		progressFrom: .18,
		progressTo: .18
	},
	{
		state: "download",
		duration: 7.5,
		progressFrom: .08,
		progressTo: .76
	},
	{
		state: "native",
		duration: 2.8,
		progressFrom: .76,
		progressTo: .76
	},
	{
		state: "thermal",
		duration: 2.8,
		progressFrom: .76,
		progressTo: .76
	},
	{
		state: "native",
		duration: 3,
		progressFrom: .46,
		progressTo: .46
	}
];
var DEMO_DURATION = DEMO_STEPS.reduce((total, step) => total + step.duration, 0);
function demoFrameAt(seconds) {
	const cycle = (seconds % DEMO_DURATION + DEMO_DURATION) % DEMO_DURATION;
	let cursor = 0;
	for (const step of DEMO_STEPS) {
		const end = cursor + step.duration;
		if (cycle < end) {
			const local = step.duration <= 0 ? 1 : (cycle - cursor) / step.duration;
			const from = step.progressFrom ?? .46;
			const to = step.progressTo ?? from;
			return {
				state: step.state,
				progress: from + (to - from) * local
			};
		}
		cursor = end;
	}
	return {
		state: "native",
		progress: .46
	};
}
function Home() {
	const demoRunning = useMachine((s) => s.demoRunning);
	const demoEpoch = useMachine((s) => s.demoEpoch);
	const applyDemoFrame = useMachine((s) => s.applyDemoFrame);
	(0, import_react.useEffect)(() => {
		if (!demoRunning) return;
		const started = performance.now();
		let raf = 0;
		const tick = () => {
			const frame = demoFrameAt((performance.now() - started) / 1e3);
			applyDemoFrame(frame.state, frame.progress);
			raf = requestAnimationFrame(tick);
		};
		raf = requestAnimationFrame(tick);
		return () => cancelAnimationFrame(raf);
	}, [
		demoRunning,
		demoEpoch,
		applyDemoFrame
	]);
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("main", { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("header", {
			className: "nav",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("a", {
				className: "brand",
				href: "#top",
				children: ["NEXBAR", /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "2" })]
			}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("nav", { children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("a", {
					href: "#native",
					children: "Native path"
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("a", {
					href: "#customize",
					children: "Control"
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("a", {
					href: "#diagnostics",
					children: "Diagnostics"
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("a", {
					href: "#install",
					children: "Install"
				})
			] })]
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
			className: "hero",
			id: "top",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "hero-copy",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
						className: "eyebrow",
						children: "Redux × SteamOS × Nollie1"
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("h1", { children: ["Make the front bar feel ", /* @__PURE__ */ (0, import_jsx_runtime.jsx)("em", { children: "native." })] }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", { children: "Steam’s own Game Mode controls when they’re available. A deterministic fallback when they aren’t. One 24-pixel bar, one source of truth." }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "hero-actions",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("a", {
							className: "primary",
							href: "/nexbar/nexbar.zip",
							children: "Get the package"
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("a", {
							className: "ghost",
							href: "#native",
							children: "See the signal path"
						})]
					})
				]
			}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "hero-meta",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("code", { children: "STEAMOS / 17 LOGICAL" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("code", { children: "REDUX / 24 PHYSICAL" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("code", { children: "NOLLIE1 / HID PRIMARY" })
				]
			})]
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Chassis, {}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "layout",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("aside", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
				className: "eyebrow",
				children: "Simulate"
			}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StateRail, {})] }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "stack",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(NativePathPanel, {}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(ControlPanel, {}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(DiagnosticsPanel, {}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(HowItWorks, {}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(InstallPanel, {})
				]
			})]
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("footer", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "NexBar2" }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "Built for the BC-250 Redux configuration." })] })
	] });
}
//#endregion
export { Home as component };
