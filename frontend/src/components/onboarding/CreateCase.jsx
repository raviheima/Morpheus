import { useState } from 'react'
function CreateCase() {
  const [formData, setFormData] = useState({
    caseName: '',
    examinerName: '',
    organisation: '',
    examinerEmail: '',
    description: '',
    examinerNotes: '',
  })
const [errors, setErrors] = useState({})
const handleSubmit = (e) => {
  e.preventDefault()

  const newErrors = {}

  if (!formData.caseName.trim()) {
    newErrors.caseName = 'Case name is required'
  }

  if (!formData.examinerName.trim()) {
    newErrors.examinerName = 'Examiner name is required'
  }

  setErrors(newErrors)

  if (Object.keys(newErrors).length === 0) {
    console.log('Case form is valid:', formData)
  }
} 
 return (
    <section className="create-case">
      <div className="create-case-header">
        <p className="eyebrow">NEW INVESTIGATION</p>

        <h1>
          Create a
          <span> case.</span>
        </h1>

        <p className="create-case-description">
          Enter the basic information for this investigation. You can add
          evidence and more details after the case has been created.
        </p>
      </div>

      <form className="case-form"
       onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="case-name">
              Case Name <span>*</span>
            </label>
            <input
              id="case-name"
              type="text"
              placeholder="e.g. Morpheus"
              value={formData.caseName}
  onChange={(e) =>
    setFormData({ ...formData, caseName: e.target.value })
  }
            />
       {errors.caseName && (
  <p className="form-error">{errors.caseName}</p>
)}
          </div>

          <div className="form-field">
            <label htmlFor="examiner-name">
              Examiner Name <span>*</span>
            </label>
            <input
              id="examiner-name"
              type="text"
              placeholder="Enter examiner name"
              value={formData.examinerName}
  onChange={(e) =>
    setFormData({ ...formData, examinerName: e.target.value })
  }
            />
{errors.examinerName && (
  <p className="form-error">{errors.examinerName}</p>
)}
          </div>

          <div className="form-field">
            <label htmlFor="organisation">Organisation</label>
            <input
              id="organisation"
              type="text"
              placeholder="Enter organisation"
              value={formData.organisation}
  onChange={(e) =>
    setFormData({ ...formData, organisation: e.target.value })
  }
            />
          </div>

          <div className="form-field">
            <label htmlFor="examiner-email">Examiner Email</label>
            <input
              id="examiner-email"
              type="email"
              placeholder="examiner@example.com"
              value={formData.examinerEmail}
  onChange={(e) =>
    setFormData({ ...formData, examinerEmail: e.target.value })
  }
            />
          </div>
        </div>

        <div className="form-field">
          <label htmlFor="description">Case Description</label>
          <textarea
            id="description"
            rows="5"
            placeholder="Briefly describe the purpose or circumstances of this investigation..."
            value={formData.description}
  onChange={(e) =>
    setFormData({ ...formData, description: e.target.value })
  }
          ></textarea>
        </div>

        <div className="form-field">
          <label htmlFor="examiner-notes">Examiner Notes</label>
          <textarea
            id="examiner-notes"
            rows="4"
            placeholder="Optional notes for this investigation..."
            value={formData.examinerNotes}
  onChange={(e) =>
    setFormData({ ...formData, examinerNotes: e.target.value })
  }
          ></textarea>
        </div>

        <div className="case-number-info">
          <div>
            <span>CASE NUMBER</span>
            <strong>AUTOMATICALLY GENERATED</strong>
          </div>

          <p>
            Leave the case number to Morpheus. A unique identifier will be
            generated when the case is created.
          </p>
        </div>

        <button type="submit" className="primary-button">
          Create Case
          <span>→</span>
        </button>
      </form>
    </section>
  )
}

export default CreateCase
