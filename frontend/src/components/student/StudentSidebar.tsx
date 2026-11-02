import { BookOpenCheck, BrainCircuit, MessageCircle, Plus } from 'lucide-react'
import type { AuthUser, SavedTutorChat } from '../../types'

type Props = {
  currentUser: AuthUser | null
  savedChats: SavedTutorChat[]
  activeChatId: string
  onStartNewChat: () => void
  onOpenChat: (chatId: string) => void
}

export function StudentSidebar({ currentUser, savedChats, activeChatId, onStartNewChat, onOpenChat }: Props) {
  return (
          <aside className="student-sidebar">
            <button
              className="student-brand"
              type="button"
            >
              <span className="brand-icon">
                <BrainCircuit size={23} />
              </span>
              <span>
                <strong>Classroom AI</strong>
                <small>Student workspace</small>
              </span>
            </button>

            <div className="student-sidebar-label">LEARNING SPACE</div>

            <button className="student-nav active">
              <MessageCircle size={17} />
              AI Tutor
            </button>

            <div className="chat-history-section">
              <div className="chat-history-heading">
                <span>YOUR CHATS</span>
                <button
                  type="button"
                  onClick={onStartNewChat}
                  aria-label="Start a new chat"
                  title="Start a new chat"
                >
                  <Plus size={16} />
                </button>
              </div>

              <div className="chat-history-list">
                {savedChats.map((chat) => (
                  <button
                    type="button"
                    key={chat.id}
                    className={`chat-history-item ${
                      chat.id === activeChatId ? 'active' : ''
                    }`}
                    onClick={() => onOpenChat(chat.id)}
                    title={chat.title}
                  >
                    <MessageCircle size={15} />
                    <span>{chat.title}</span>
                  </button>
                ))}
              </div>
            </div>


            <div className="student-course-card">
              <BookOpenCheck size={19} />
              <strong>Course learning</strong>
              <p>Ask questions about your uploaded learning materials.</p>
            </div>

            <div className="student-profile">
              <span className="student-avatar">S</span>
              <span>
                <strong>{currentUser?.email ?? 'Student'}</strong>
                <small>Student workspace</small>
              </span>
            </div>
          </aside>
  )
}
