import { useState } from 'react'
import { ChevronDown, LogOut, UserRound } from 'lucide-react'
import type { AuthUser } from '../../types'

type Props = { user: AuthUser; onLogout: () => void }

export function ProfileMenu({ user, onLogout }: Props) {
  const [open, setOpen] = useState(false)
  return (
    <div className="profile-menu">
      <button className="profile-menu-trigger" type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <span className="profile-menu-avatar"><UserRound size={17} /></span>
        <span className="profile-menu-identity"><strong>{user.email}</strong><small>{user.role === 'professor' ? 'Professor' : 'Student'}</small></span>
        <ChevronDown size={16} />
      </button>
      {open && (
        <div className="profile-menu-popover">
          <div className="profile-menu-details"><strong>{user.email}</strong><small>{user.user_id}</small></div>
          <button type="button" onClick={onLogout}><LogOut size={16} /> Log out</button>
        </div>
      )}
    </div>
  )
}
