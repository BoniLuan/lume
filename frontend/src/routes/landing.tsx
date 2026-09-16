import { ArrowRight, BarChart3, Check, Gauge, ListPlus } from "lucide-react";
import { Link } from "react-router-dom";

export function LandingRoute() {
  return (
    <div className="landing">
      <header className="landing-nav"><Link to="/" className="brand"><img src="/lume-mark.svg" alt="" /><span>Lume</span></Link><nav><a href="#approach">How it works</a><a href="#privacy">Privacy</a><Link className="button button-primary button-md" to="/login">Sign in</Link></nav></header>
      <main>
        <section className="hero">
          <div className="hero-copy"><span className="eyebrow">Clarity for everyday money</span><h1>See your spending.<br /><em>Shape what comes next.</em></h1><p>Lume turns daily transactions into a calm, useful view of where your money goes and how your month is tracking.</p><div className="hero-actions"><Link className="button button-primary button-lg" to="/login">Open Lume <ArrowRight size={18} /></Link><a className="text-link" href="#approach">Explore the approach</a></div><div className="trust-line"><Check size={17} /> Your data stays private and under your control.</div></div>
          <div className="hero-card" aria-label="Example monthly overview"><div className="hero-card-top"><span>September overview</span><span className="status-pill">On track</span></div><div className="hero-balance"><small>Available after spending</small><strong>R$ 3,248.70</strong><span>+ R$ 620.40 this month</span></div><div className="hero-progress"><div><span>Monthly budget</span><b>62%</b></div><div className="progress"><i style={{ width: "62%" }} /></div><small>R$ 1,902.00 remaining</small></div><div className="hero-list"><div><span className="category-icon">F</span><p><b>Food & dining</b><small>14 transactions</small></p><strong>R$ 684.20</strong></div><div><span className="category-icon">H</span><p><b>Home</b><small>5 transactions</small></p><strong>R$ 421.00</strong></div><div><span className="category-icon">T</span><p><b>Transport</b><small>9 transactions</small></p><strong>R$ 286.50</strong></div></div></div>
        </section>
        <section id="approach" className="feature-section"><span className="eyebrow">One clear rhythm</span><h2>Record quickly. Understand immediately.</h2><div className="feature-grid"><article><ListPlus /><h3>Capture in seconds</h3><p>A phone-first entry flow keeps amount, account, category, and date close at hand.</p></article><article><Gauge /><h3>Know your pace</h3><p>Compare spending with your monthly intention before the month gets away from you.</p></article><article><BarChart3 /><h3>Notice the pattern</h3><p>Focused comparisons reveal categories and changes that deserve your attention.</p></article></div></section>
        <section id="privacy" className="privacy-panel"><div><span className="eyebrow">Built with restraint</span><h2>Your finances are personal.</h2></div><p>Lume uses secure server sessions, strict ownership checks, and avoids third-party tracking. It shows the facts without selling attention.</p></section>
      </main>
      <footer><span>© {new Date().getFullYear()} Lume</span><span>Personal finance, made visible.</span></footer>
    </div>
  );
}
