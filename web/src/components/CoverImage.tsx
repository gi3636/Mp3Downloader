import { useEffect, useState } from 'react'

interface Props {
  src?: string | null
  className?: string
  alt?: string
}

export function CoverImage({ src, className, alt }: Props) {
  const [error, setError] = useState(false)

  useEffect(() => {
    setError(false)
  }, [src])

  if (!src || error) {
    return <div className={`${className || ''} cover-placeholder`} aria-hidden="true" />
  }

  return (
    <img
      className={className}
      alt={alt || ''}
      src={src}
      onError={() => {
        setError(true)
      }}
    />
  )
}
