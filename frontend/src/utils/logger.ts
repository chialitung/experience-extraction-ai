/**
 * 统一前端日志工具。
 *
 * 开发环境输出到 console，生产环境可扩展为上报到后端或第三方服务。
 * 支持 info / warn / error / debug 四级日志，自动附加时间戳和上下文。
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogContext {
  [key: string]: unknown;
}

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: LogContext;
}

class Logger {
  private static instance: Logger;
  private level: LogLevel;
  private isDev: boolean;

  private constructor() {
    this.level = (import.meta.env.VITE_LOG_LEVEL as LogLevel) || 'info';
    this.isDev = import.meta.env.DEV;
  }

  static getInstance(): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger();
    }
    return Logger.instance;
  }

  private shouldLog(level: LogLevel): boolean {
    const levels: Record<LogLevel, number> = {
      debug: 0,
      info: 1,
      warn: 2,
      error: 3,
    };
    return levels[level] >= levels[this.level];
  }

  /** 深度清理 context，移除函数、DOM 节点、循环引用等不可序列化内容 */
  private safeCloneContext(context?: LogContext): LogContext | undefined {
    if (!context) return undefined;
    const seen = new WeakSet<object>();
    const clone = (value: unknown): unknown => {
      if (value === null || typeof value === 'boolean' || typeof value === 'number' || typeof value === 'string') {
        return value;
      }
      if (typeof value === 'function') {
        return '[Function]';
      }
      if (value instanceof Error) {
        return { name: value.name, message: value.message, stack: value.stack };
      }
      if (value && typeof (value as any).nodeType === 'number') {
        // DOM Element / Node
        return `[DOM ${(value as any).nodeName || 'Node'}]`;
      }
      if (typeof value === 'object') {
        if (seen.has(value)) {
          return '[Circular]';
        }
        seen.add(value);
        if (Array.isArray(value)) {
          return value.map(clone);
        }
        const result: Record<string, unknown> = {};
        for (const key of Object.keys(value)) {
          try {
            result[key] = clone((value as Record<string, unknown>)[key]);
          } catch {
            result[key] = '[Unserializable]';
          }
        }
        return result;
      }
      return String(value);
    };
    return clone(context) as LogContext;
  }

  private formatMessage(level: LogLevel, message: string, context?: LogContext): LogEntry {
    return {
      timestamp: new Date().toISOString(),
      level,
      message,
      context: this.safeCloneContext(context),
    };
  }

  private output(entry: LogEntry): void {
    if (!this.isDev) {
      // 生产环境：可在此处扩展上报逻辑（如发送到后端 / Sentry / 阿里云日志等）
      // 当前仅静默丢弃 debug，保留 error/warn
      if (entry.level === 'debug' || entry.level === 'info') return;
      // 生产环境将 error/warn 暂存到 localStorage 供调试
      try {
        const logs = JSON.parse(localStorage.getItem('app_logs') || '[]');
        logs.push(entry);
        // 只保留最近 100 条
        if (logs.length > 100) logs.shift();
        localStorage.setItem('app_logs', JSON.stringify(logs));
      } catch {
        // ignore
      }
      return;
    }

    const prefix = `[${entry.timestamp.slice(11, 19)}] [${entry.level.toUpperCase()}]`;
    const args: unknown[] = [`${prefix} ${entry.message}`];
    if (entry.context && Object.keys(entry.context).length > 0) {
      args.push(entry.context);
    }

    switch (entry.level) {
      case 'debug':
        console.debug(...args);
        break;
      case 'info':
        console.info(...args);
        break;
      case 'warn':
        console.warn(...args);
        break;
      case 'error':
        console.error(...args);
        break;
    }
  }

  debug(message: string, context?: LogContext): void {
    if (this.shouldLog('debug')) {
      this.output(this.formatMessage('debug', message, context));
    }
  }

  info(message: string, context?: LogContext): void {
    if (this.shouldLog('info')) {
      this.output(this.formatMessage('info', message, context));
    }
  }

  warn(message: string, context?: LogContext): void {
    if (this.shouldLog('warn')) {
      this.output(this.formatMessage('warn', message, context));
    }
  }

  error(message: string, context?: LogContext): void {
    if (this.shouldLog('error')) {
      this.output(this.formatMessage('error', message, context));
    }
  }

  /** 获取本地缓存的日志（用于用户报障时导出） */
  getStoredLogs(): LogEntry[] {
    try {
      return JSON.parse(localStorage.getItem('app_logs') || '[]');
    } catch {
      return [];
    }
  }

  /** 清空本地缓存日志 */
  clearStoredLogs(): void {
    localStorage.removeItem('app_logs');
  }
}

export const logger = Logger.getInstance();
