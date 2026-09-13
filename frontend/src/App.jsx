import { useState } from 'react'
import './App.css'

function App() {
const [showWelcome, setShowWelcome] = useState(false)
  if (showWelcome) {
  return (
    <main className="app onboarding">
      <nav className="navbar">
        <div className="brand">
          <div className="brand-mark">M</div>
          <span>MORPHEUS</span>
        </div>

        <div className="nav-status">
          <span className="status-dot"></span>
          FORENSIC WORKSPACE
        </div>
      </nav>

      <section className="welcome-screen">
        <p className="eyebrow">WELCOME TO MORPHEUS</p>

        <h1>
          Start your
          <span> investigation.</span>
        </h1>

        <p className="hero-description">
          Before you begin, take a moment to understand how Morpheus
          protects evidence and keeps your investigation accountable.
        </p>

        <div className="guidelines">
          <div className="guideline">
            <span>01</span>
            <div>
              <h3>Preserve the original</h3>
              <p>
                Register evidence and verify its integrity without
                unnecessarily altering the original source.
              </p>
            </div>
          </div>

          <div className="guideline">
            <span>02</span>
            <div>
              <h3>Every action matters</h3>
              <p>
                Important evidence activity is recorded so the chain of
                custody remains clear and accountable.
              </p>
            </div>
          </div>

          <div className="guideline">
            <span>03</span>
            <div>
              <h3>Verify before you investigate</h3>
              <p>
                Use integrity information such as cryptographic hashes to
                help confirm that evidence has not changed unexpectedly.
              </p>
            </div>
          </div>
        </div>

        <div className="welcome-actions">
          <button className="primary-button">
            Create a Case
            <span>→</span>
          </button>

          <button
            className="secondary-button"
            onClick={() => setShowWelcome(false)}
          >
            Back
          </button>
        </div>
      </section>
    </main>
  )
}

return (
  <main className="app">
      <nav className="navbar">
        <div className="brand">
          <div className="brand-mark">M</div>
          <span>MORPHEUS</span>
        </div>

        <div className="nav-status">
          <span className="status-dot"></span>
          FORENSIC WORKSPACE
        </div>
      </nav>

      <section className="hero">
        <div className="hero-content">
          <p className="eyebrow">DIGITAL FORENSICS • EVIDENCE INTEGRITY</p>

          <h1>
            Investigate with
            <span> confidence.</span>
          </h1>

          <p className="hero-description">
            Morpheus is a unified digital forensics workspace built to
            preserve evidence, track every action, and turn complex findings
            into a clear investigative story.
          </p>

          <div className="hero-actions">
            <button
              className="primary-button"
              onClick={() => setShowWelcome(true)}
            >
              Get Started
              <span>→</span>
            </button>
            <button className="secondary-button">
              Learn how it works
            </button>
          </div>
        </div>

        <div className="hero-visual">
          <div className="scan-line"></div>

          <div className="evidence-card">
            <div className="card-header">
              <span>EVIDENCE PASSPORT</span>
              <span className="verified">VERIFIED</span>
            </div>

            <div className="evidence-id">
              <small>EVIDENCE ID</small>
              <strong>MRP-EV-0001</strong>
            </div>

            <div className="hash-block">
              <small>SHA-256 INTEGRITY HASH</small>
              <code>
                7f83b1657ff1fc53...
                <br />
                9a3d84c7b1e2a601
              </code>
            </div>

            <div className="card-footer">
              <span>INTEGRITY STATUS</span>
              <strong>✓ INTACT</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="principles">
        <div className="section-heading">
          <p className="eyebrow">BUILT FOR THE INVESTIGATION</p>
          <h2>Evidence tells the story.</h2>
          <p>
            Every part of Morpheus is designed around the integrity and
            accountability of digital evidence.
          </p>
        </div>

        <div className="principle-grid">
          <article className="principle-card">
            <div className="card-number">01</div>
            <h3>Preserve Evidence</h3>
            <p>
              Register evidence and verify its integrity with cryptographic
              hashes without unnecessarily duplicating the original file.
            </p>
          </article>

          <article className="principle-card">
            <div className="card-number">02</div>
            <h3>Track Every Action</h3>
            <p>
              Maintain a clear chain of custody so every important interaction
              with evidence can be accounted for.
            </p>
          </article>

          <article className="principle-card">
            <div className="card-number">03</div>
            <h3>Build the Story</h3>
            <p>
              Transform technical findings into an understandable timeline
              that helps investigators explain what happened.
            </p>
          </article>
        </div>
      </section>

      <footer className="footer">
        <span>MORPHEUS</span>
        <span>UNIFIED DIGITAL FORENSICS</span>
      </footer>
    </main>
  )
}

export default App
