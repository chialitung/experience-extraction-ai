import { Link } from 'react-router-dom';
import { MessageSquare, Sparkles, BookOpen, ArrowRight } from 'lucide-react';

export function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white">
      <div className="max-w-6xl mx-auto px-6 py-16">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-gray-900 mb-6">
            经验萃取AI
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
            将业务专家的隐性经验转化为可复制的显性知识。
            通过AI驱动的结构化访谈，系统化地完成经验萃取。
          </p>
          <Link
            to="/interviews/new"
            className="inline-flex items-center px-8 py-4 bg-primary-600 text-white rounded-lg font-semibold hover:bg-primary-700 transition-colors"
          >
            <Sparkles className="w-5 h-5 mr-2" />
            开始新的萃取访谈
            <ArrowRight className="w-5 h-5 ml-2" />
          </Link>
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-8 mb-16">
          <FeatureCard
            icon={MessageSquare}
            title="智能访谈引导"
            description="AI根据六步流程自动提问，深度挖掘专家经验，确保不遗漏关键细节。"
          />
          <FeatureCard
            icon={BookOpen}
            title="实时结构化萃取"
            description="访谈过程中自动提取步骤、工具、风险点，实时构建知识框架。"
          />
          <FeatureCard
            icon={Sparkles}
            title="成果自动封装"
            description="访谈结束后自动生成话术卡、检查表、流程图等可直接使用的工具。"
          />
        </div>

        {/* Process */}
        <div className="bg-white rounded-2xl shadow-sm p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-8 text-center">
            萃取流程
          </h2>
          <div className="flex items-center justify-between">
            {[
              { step: '1', name: '配置访谈', desc: '设定主题与目标' },
              { step: '2', name: '生成蓝图', desc: 'AI规划访谈路径' },
              { step: '3', name: '深度访谈', desc: '多轮对话萃取' },
              { step: '4', name: '成果输出', desc: '自动生成工具' },
            ].map((item, index) => (
              <div key={item.step} className="flex items-center">
                <div className="text-center">
                  <div className="w-12 h-12 bg-primary-100 text-primary-600 rounded-full flex items-center justify-center text-lg font-bold mx-auto mb-3">
                    {item.step}
                  </div>
                  <h3 className="font-semibold text-gray-900">{item.name}</h3>
                  <p className="text-sm text-gray-500">{item.desc}</p>
                </div>
                {index < 3 && (
                  <ArrowRight className="w-6 h-6 text-gray-300 mx-8" />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function FeatureCard({ icon: Icon, title, description }: {
  icon: React.ElementType;
  title: string;
  description: string;
}) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
      <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
        <Icon className="w-6 h-6 text-primary-600" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  );
}
