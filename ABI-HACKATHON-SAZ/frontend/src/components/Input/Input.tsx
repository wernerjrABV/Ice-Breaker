import { useId, type InputHTMLAttributes } from 'react'
import './Input.css'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

function Input({ label, className = '', ...rest }: InputProps) {
  const id = useId()

  return (
    <div className={`input-group ${className}`.trim()}>
      {label && (
        <label className="input-label" htmlFor={id}>
          {label}
        </label>
      )}
      <input id={id} className="input" {...rest} />
    </div>
  )
}

export default Input
