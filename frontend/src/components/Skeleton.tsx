function SkeletonBase({ className = '' }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-gray-200 rounded ${className}`} />
  );
}

/** 访谈列表页骨架屏 */
export function InterviewListSkeleton() {
  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* 标题区 */}
      <div className="flex items-center justify-between">
        <div>
          <SkeletonBase className="h-8 w-32 mb-2" />
          <SkeletonBase className="h-4 w-48" />
        </div>
        <SkeletonBase className="h-10 w-28" />
      </div>
      {/* 搜索+筛选 */}
      <div className="flex gap-3">
        <SkeletonBase className="h-10 flex-1" />
        <SkeletonBase className="h-10 w-32" />
      </div>
      {/* 卡片列表 */}
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="bg-white rounded-xl border p-5 space-y-3">
          <div className="flex items-center justify-between">
            <SkeletonBase className="h-5 w-48" />
            <SkeletonBase className="h-5 w-16" />
          </div>
          <SkeletonBase className="h-4 w-full" />
          <SkeletonBase className="h-4 w-3/4" />
          <div className="flex gap-2 pt-2">
            <SkeletonBase className="h-8 w-20" />
            <SkeletonBase className="h-8 w-20" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** 访谈详情/输出页骨架屏 */
export function OutputPageSkeleton() {
  return (
    <div className="max-w-4xl mx-auto p-8 space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SkeletonBase className="h-10 w-10 rounded-lg" />
          <div>
            <SkeletonBase className="h-6 w-32 mb-1" />
            <SkeletonBase className="h-4 w-48" />
          </div>
        </div>
        <div className="flex gap-2">
          <SkeletonBase className="h-9 w-20" />
          <SkeletonBase className="h-9 w-20" />
        </div>
      </div>
      {/* 内容区 */}
      <div className="bg-white rounded-xl border p-6 space-y-6">
        <SkeletonBase className="h-8 w-1/2 mx-auto" />
        <SkeletonBase className="h-4 w-1/3 mx-auto" />
        <div className="space-y-4 pt-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-start gap-3">
              <SkeletonBase className="h-7 w-7 rounded-full flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <SkeletonBase className="h-4 w-3/4" />
                <SkeletonBase className="h-4 w-full" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** 通用卡片骨架 */
export function CardSkeleton({ count = 1 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-white rounded-xl border p-5 space-y-3">
          <SkeletonBase className="h-5 w-2/3" />
          <SkeletonBase className="h-4 w-full" />
          <SkeletonBase className="h-4 w-4/5" />
        </div>
      ))}
    </>
  );
}

/** 通用文本骨架 */
export function TextSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonBase
          key={i}
          className={`h-4 ${i === lines - 1 ? 'w-3/4' : 'w-full'}`}
        />
      ))}
    </div>
  );
}
