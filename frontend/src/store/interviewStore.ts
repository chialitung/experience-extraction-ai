import { create } from 'zustand';
import type { Interview, Message, StructuredContent, Blueprint, ExpertProfile, ContentAnalysis } from '@/types';

export interface TimingState {
  status: 'stopped' | 'running' | 'paused' | 'completed';
  elapsedSeconds: number;
}

interface RecordingState {
  isActive: boolean;
  deviceId: string | null;
  segmentCount: number;
}

interface InterviewState {
  // Current interview
  currentInterview: Interview | null;
  messages: Message[];
  structuredContent: StructuredContent;
  blueprint: Blueprint | null;
  expertProfile: ExpertProfile | null;
  latestAnalysis: ContentAnalysis | null;
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;

  // Timer & Recording
  timing: TimingState;
  recording: RecordingState;

  // Actions
  setCurrentInterview: (interview: Interview | null) => void;
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  setStructuredContent: (content: StructuredContent) => void;
  updateStructuredContent: (content: Partial<StructuredContent>) => void;
  setBlueprint: (blueprint: Blueprint | null) => void;
  setExpertProfile: (profile: ExpertProfile | null) => void;
  setLatestAnalysis: (analysis: ContentAnalysis | null) => void;
  setIsLoading: (loading: boolean) => void;
  setIsStreaming: (streaming: boolean) => void;
  setError: (error: string | null) => void;
  setTiming: (timing: Partial<TimingState>) => void;
  setRecording: (recording: Partial<RecordingState>) => void;
  reset: () => void;
}

const initialStructuredContent: StructuredContent = {
  steps: [],
  principles: [],
  tools: [],
  risks: [],
  decisions: [],
};

const initialTiming: TimingState = {
  status: 'stopped',
  elapsedSeconds: 0,
};

const initialRecording: RecordingState = {
  isActive: false,
  deviceId: null,
  segmentCount: 0,
};

export const useInterviewStore = create<InterviewState>((set) => ({
  currentInterview: null,
  messages: [],
  structuredContent: initialStructuredContent,
  blueprint: null,
  expertProfile: null,
  latestAnalysis: null,
  isLoading: false,
  isStreaming: false,
  error: null,

  timing: initialTiming,
  recording: initialRecording,

  setCurrentInterview: (interview) => set({ currentInterview: interview }),

  setMessages: (messages) => set({ messages }),

  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message],
  })),

  updateMessage: (id, updates) => set((state) => ({
    messages: state.messages.map((msg) =>
      msg.id === id ? { ...msg, ...updates } : msg
    ),
  })),

  setStructuredContent: (content) => set({ structuredContent: content }),

  updateStructuredContent: (content) => set((state) => ({
    structuredContent: { ...state.structuredContent, ...content },
  })),

  setBlueprint: (blueprint) => set({ blueprint }),

  setExpertProfile: (expertProfile) => set({ expertProfile }),

  setLatestAnalysis: (latestAnalysis) => set({ latestAnalysis }),

  setIsLoading: (isLoading) => set({ isLoading }),

  setIsStreaming: (isStreaming) => set({ isStreaming }),

  setError: (error) => set({ error }),

  setTiming: (timing) => set((state) => ({
    timing: { ...state.timing, ...timing },
  })),

  setRecording: (recording) => set((state) => ({
    recording: { ...state.recording, ...recording },
  })),

  reset: () => set({
    currentInterview: null,
    messages: [],
    structuredContent: initialStructuredContent,
    blueprint: null,
    expertProfile: null,
    latestAnalysis: null,
    isLoading: false,
    isStreaming: false,
    error: null,
    timing: initialTiming,
    recording: initialRecording,
  }),
}));
