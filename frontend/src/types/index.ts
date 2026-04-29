export interface ExpertProfile {
  profile_type: string;
  type_label_cn: string;
  confidence: number;
  evidence: Record<string, any>;
  adaptation_strategy: string;
  suggestion: string;
}

export interface ContentAnalysis {
  depth: string;
  depth_score: number;
  depth_reason: string;
  off_topic: boolean;
  off_topic_confidence: number;
  off_topic_reason: string;
  gaps: string[];
  gap_reason: string;
}

export interface Interview {
  id: string;
  theme: string;
  background?: string;
  expert_role?: string;
  expected_duration?: number;
  target_output_format: string[];
  blueprint: Record<string, any>;
  current_state: string;
  state_history: any[];
  expert_profile: ExpertProfile | Record<string, any>;
  value_assessment: Record<string, any>;
  final_output: Record<string, any>;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  interview_id: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
  message_type?: string;
  question_type?: string;
  extracted_data?: Record<string, any>;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface StructuredContent {
  steps: StepItem[];
  principles: PrincipleItem[];
  tools: ToolItem[];
  risks: RiskItem[];
  decisions: any[];
}

export interface StepItem {
  order: number;
  title: string;
  description: string;
  details?: string;
  // 兼容旧数据格式
  name?: string;
  detail?: string;
}

export interface PrincipleItem {
  title: string;
  description: string;
  application_scenario?: string;
  // 兼容旧数据格式
  name?: string;
  detail?: string;
}

export interface ToolItem {
  name: string;
  description: string;
  usage_method?: string;
  // 兼容旧数据格式
  title?: string;
  detail?: string;
}

export interface RiskItem {
  type: string;
  description: string;
  prevention?: string;
  // 兼容旧数据格式
  name?: string;
  detail?: string;
}

export interface InterviewCreateRequest {
  theme: string;
  background?: string;
  expert_role?: string;
  expected_duration?: number;
  target_output_format?: string[];
}

export interface Blueprint {
  theme: string;
  value_assessment: {
    gold: number;
    wood: number;
    water: number;
    fire: number;
    earth: number;
    reasons: Record<string, string>;
  };
  six_steps: BlueprintStep[];
  target_output: string;
  overall_strategy: string;
}

export interface BlueprintStep {
  step: string;
  step_name: string;
  duration_min: number;
  objectives: string[];
  key_questions: {
    type: string;
    question: string;
    purpose: string;
  }[];
}

export const InterviewStates = [
  { key: 'event_review', name: '复盘事件', description: '获取成功案例背景' },
  { key: 'framework_build', name: '建构框架', description: '识别核心步骤框架' },
  { key: 'detail_mining', name: '挖掘细节', description: '深挖每个步骤的具体动作' },
  { key: 'obstacle_identify', name: '识别障碍', description: '识别易错点、困难点' },
  { key: 'tool_extract', name: '提炼工具', description: '提炼可操作的工具/话术' },
  { key: 'confirmation', name: '复述确认', description: '总结确认，专家审核' },
  { key: 'completed', name: '已完成', description: '访谈结束' },
] as const;

export const OutputFormats = [
  { value: 'comprehensive', label: '全套素材包', description: '一次性生成全部5种形式' },
  { value: 'script_card', label: '话术卡', description: '标准话术与应对策略' },
  { value: 'checklist', label: '检查表', description: '操作步骤检查清单' },
  { value: 'flowchart', label: '流程图', description: '决策流程与步骤' },
  { value: 'learning_card', label: '学习卡', description: '知识点速记卡片' },
  { value: 'case_study', label: '案例', description: '完整案例分析' },
] as const;

// ==================== Auth Types ====================

export interface User {
  id: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}
