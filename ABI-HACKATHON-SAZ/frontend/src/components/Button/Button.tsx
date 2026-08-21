import type { ButtonHTMLAttributes } from 'react'
import './Button.css'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost'
}

function Button({ children, variant = 'primary', className = '', ...rest }: ButtonProps) {
  return (
    <button type="button" className={`button button-${variant} ${className}`.trim()} {...rest}>
      {children}
    </button>
  )
}

export default Button
