import { useEffect, useState } from 'react'
import { apiFetch } from '../services/api'
import type { ChatMessage, SavedTutorChat, TutorResponse } from '../types'

const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Hi! I'm your AI Tutor. Ask me anything about your course materials, and I'll help you understand the concepts step by step.",
}

function getChatStorageKey(userId: string, courseId: string) {
  return `classroom-ai-tutor-chats-${userId}-${courseId}`
}

function createNewChat(): SavedTutorChat {
  return {
    id: `chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: 'New conversation',
    sessionId: `demo-session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    messages: [{ ...WELCOME_MESSAGE }],
    updatedAt: Date.now(),
  }
}

function loadSavedChats(userId: string, courseId: string): SavedTutorChat[] {
  try {
    const saved = localStorage.getItem(getChatStorageKey(userId, courseId))

    if (saved) {
      const parsed: unknown = JSON.parse(saved)
      if (
        Array.isArray(parsed) &&
        parsed.every(
          (chat: unknown) =>
            typeof chat === 'object' &&
            chat !== null &&
            'id' in chat &&
            typeof chat.id === 'string' &&
            'title' in chat &&
            typeof chat.title === 'string' &&
            'sessionId' in chat &&
            typeof chat.sessionId === 'string' &&
            'messages' in chat &&
            Array.isArray(chat.messages) &&
            'updatedAt' in chat &&
            typeof chat.updatedAt === 'number',
        )
      ) {
        return parsed as SavedTutorChat[]
      }
    }
  } catch {
    console.error('Unable to load saved tutor chats.')
  }

  return [createNewChat()]
}

export function useTutorChats(userId: string | null, courseId: string | null) {
  const [savedChats, setSavedChats] = useState<SavedTutorChat[]>([])
  const [activeChatId, setActiveChatId] = useState('')
  const [chatsLoadedForUser, setChatsLoadedForUser] = useState<string | null>(null)
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatError, setChatError] = useState('')

  useEffect(() => {
    if (!userId || !courseId) {
      setSavedChats([])
      setActiveChatId('')
      setChatsLoadedForUser(null)
      setChatInput('')
      setChatError('')
      setChatLoading(false)
      return
    }

    const userChats = loadSavedChats(userId, courseId)
    setSavedChats(userChats)
    setActiveChatId(userChats[0]?.id ?? '')
    setChatsLoadedForUser(`${userId}:${courseId}`)
    setChatInput('')
    setChatError('')
  }, [userId, courseId])

  useEffect(() => {
    if (!userId || !courseId || chatsLoadedForUser !== `${userId}:${courseId}`) return

    try {
      localStorage.setItem(getChatStorageKey(userId, courseId), JSON.stringify(savedChats))
    } catch (error) {
      console.error('Unable to save tutor chat history:', error)
    }
  }, [savedChats, userId, courseId, chatsLoadedForUser])

  const activeChat =
    savedChats.find((chat) => chat.id === activeChatId) ?? savedChats[0]
  const chatMessages = activeChat?.messages ?? []
  const sessionId = activeChat?.sessionId ?? ''

  function updateActiveChat(updater: (chat: SavedTutorChat) => SavedTutorChat) {
    setSavedChats((previous) =>
      previous.map((chat) => (chat.id === activeChatId ? updater(chat) : chat)),
    )
  }

  function startNewChat() {
    const newChat = createNewChat()
    setSavedChats((previous) => [newChat, ...previous])
    setActiveChatId(newChat.id)
    setChatInput('')
    setChatError('')
  }

  function openChat(chatId: string) {
    setActiveChatId(chatId)
    setChatInput('')
    setChatError('')
  }

  async function sendTutorMessage() {
    const message = chatInput.trim()
    if (!message || chatLoading || !userId || !courseId || !activeChat) return

    setChatInput('')
    setChatError('')
    setChatLoading(true)

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
    }

    updateActiveChat((chat) => ({
      ...chat,
      title:
        chat.title === 'New conversation'
          ? message.slice(0, 45) + (message.length > 45 ? '…' : '')
          : chat.title,
      messages: [...chat.messages, userMessage],
      updatedAt: Date.now(),
    }))

    try {
      const response = await apiFetch('/api/tutor/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_id: courseId,
          session_id: sessionId,
          message,
          top_k: 5,
        }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'The tutor could not answer your question.',
        )
      }

      const result = data as TutorResponse
      if (typeof result.answer !== 'string') {
        throw new Error('The tutor returned an unexpected response.')
      }

      updateActiveChat((chat) => ({
        ...chat,
        messages: [
          ...chat.messages,
          {
            id: `assistant-${Date.now()}`,
            role: 'assistant',
            content: result.answer,
            sources: result.sources ?? [],
          },
        ],
        updatedAt: Date.now(),
      }))
    } catch (error) {
      setChatError(
        error instanceof Error
          ? error.message
          : 'Unable to connect to the Tutor Agent.',
      )
      setChatInput(message)
    } finally {
      setChatLoading(false)
    }
  }

  return {
    savedChats,
    activeChatId,
    chatMessages,
    chatInput,
    setChatInput,
    chatLoading,
    chatError,
    startNewChat,
    openChat,
    sendTutorMessage,
  }
}
