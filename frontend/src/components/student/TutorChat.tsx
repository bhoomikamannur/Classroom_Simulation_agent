import { AlertCircle, ArrowLeft, BookOpenCheck, Bot, FileText, LoaderCircle, Plus, Send, UserRound } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import type { ChatMessage } from '../../types'

type Props = {
  onLogout: () => void
  chatMessages: ChatMessage[]
  chatLoading: boolean
  chatError: string
  chatInput: string
  onStartNewChat: () => void
  onChatInputChange: (value: string) => void
  onSendMessage: () => void
}

export function TutorChat({ onLogout, chatMessages, chatLoading, chatError, chatInput, onStartNewChat, onChatInputChange, onSendMessage }: Props) {
  return (
          <div className="chat-workspace">
            <header className="chat-header">
              <button
                className="chat-back"
                type="button"
                onClick={onLogout}
                aria-label="Log out"
                title="Log out"
              >
                <ArrowLeft size={16} />
              </button>

              <span className="chat-agent-icon">
                <Bot size={23} />
              </span>

              <div className="chat-header-copy">
                <strong>AI Learning Tutor</strong>
                <span>
                  <span className="status-dot" />
                  Course-aware learning assistant
                </span>
              </div>

              <button
                className="new-chat-button"
                disabled={chatLoading}
                onClick={onStartNewChat}
              >
                <Plus size={16} />
                <span>New chat</span>
              </button>
            </header>

            <div className="chat-context-banner">
              <BookOpenCheck size={17} />
              <span>
                <strong>Learning from course materials</strong>
                <small>
                  Answers use retrieved course content when relevant.
                </small>
              </span>
            </div>

            <div className="chat-messages" aria-live="polite">
              {chatMessages.map((message) => (
                <article
                  className={`chat-message ${message.role}`}
                  key={message.id}
                >
                  <span className={`message-avatar ${message.role}`}>
                    {message.role === 'assistant'
                      ? <Bot size={18} />
                      : <UserRound size={18} />}
                  </span>

                  <div className="message-body">
                    <span className="message-author">
                      {message.role === 'assistant'
                        ? 'AI Tutor'
                        : 'You'}
                    </span>

                    <div className="message-bubble">
                      {message.role === 'assistant' ? (
                        <ReactMarkdown>{message.content}</ReactMarkdown>
                      ) : (
                        message.content
                      )}
                    </div>

                    {message.role === 'assistant' &&
                      message.sources &&
                      message.sources.length > 0 && (
                        <div className="source-list">
                          <span className="source-heading">
                            <BookOpenCheck size={14} />
                            Retrieved course sources
                          </span>

                          {message.sources.map((source, index) => {
                            const rawName =
                              typeof source.source_name === 'string'
                                ? source.source_name
                                : 'Course material'

                            const name = rawName.split(/[\\/]/).pop() || 'Course material'

                            const location =
                              source.page != null
                                ? `Page ${String(source.page)}`
                                : source.slide != null
                                  ? `Slide ${String(source.slide)}`
                                  : ''

                            return (
                              <div
                                className="source-chip"
                                key={`${name}-${location}-${index}`}
                              >
                                <FileText size={14} />
                                <span>{name}</span>
                                {location && <small>{location}</small>}
                              </div>
                            )
                          })}
                        </div>
                      )}
                  </div>
                </article>
              ))}

              {chatLoading && (
                <div className="typing-indicator" role="status">
                  <span className="message-avatar assistant">
                    <Bot size={18} />
                  </span>
                  <div>
                    <span className="message-author">AI Tutor</span>
                    <div className="typing-bubble">
                      <LoaderCircle className="spin" size={17} />
                      Thinking through your question...
                    </div>
                  </div>
                </div>
              )}
            </div>

            {chatError && (
              <div className="chat-error" role="alert">
                <AlertCircle size={16} />
                <span>{chatError}</span>
              </div>
            )}

            <form
              className="chat-composer"
              onSubmit={(event) => {
                event.preventDefault()
                void onSendMessage()
              }}
            >
              <textarea
                value={chatInput}
                onChange={(event) => onChatInputChange(event.target.value)}
                onKeyDown={(event) => {
                  if (
                    event.key === 'Enter' &&
                    !event.shiftKey &&
                    !event.nativeEvent.isComposing
                  ) {
                    event.preventDefault()
                    void onSendMessage()
                  }
                }}
                placeholder="Ask a question about your course..."
                aria-label="Message the AI Tutor"
                rows={2}
                disabled={chatLoading}
              />

              <div className="composer-footer">
                <span>Enter to send · Shift + Enter for a new line</span>

                <button
                  type="submit"
                  className="send-button"
                  disabled={!chatInput.trim() || chatLoading}
                  aria-label="Send message"
                >
                  {chatLoading
                    ? <LoaderCircle className="spin" size={18} />
                    : <Send size={18} />}
                </button>
              </div>
            </form>

            <p className="chat-disclaimer">
              AI-generated explanations may need verification against your course material.
            </p>
          </div>
  )
}
