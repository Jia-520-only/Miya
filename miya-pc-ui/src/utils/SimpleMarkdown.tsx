/**
 * 简单的 Markdown 渲染组件
 * 作为 react-markdown 的临时替代方案
 */

interface SimpleMarkdownProps {
  content: string;
  className?: string;
}

export default function SimpleMarkdown({ content, className = '' }: SimpleMarkdownProps) {
  if (!content) return null;

  // 简单的 Markdown 转换
  const html = content
    // 标题
    .replace(/^### (.*$)/gim, '<h3 class="text-xl font-bold mt-6 mb-3">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 class="text-2xl font-bold mt-6 mb-3">$1</h2>')
    .replace(/^# (.*$)/gim, '<h1 class="text-3xl font-bold mt-6 mb-3">$1</h1>')
    // 粗体和斜体
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>')
    // 代码块
    .replace(/```([\s\S]*?)```/g, '<pre class="bg-gray-900 text-gray-100 p-4 rounded-lg my-4 overflow-x-auto"><code>$1</code></pre>')
    .replace(/`(.*?)`/g, '<code class="bg-gray-200 dark:bg-gray-700 px-1 rounded">$1</code>')
    // 链接
    .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" class="text-blue-600 hover:text-blue-800 underline" target="_blank" rel="noopener noreferrer">$1</a>')
    // 图片
    .replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" class="max-w-full h-auto rounded-lg my-4" />')
    // 列表
    .replace(/^\- (.*$)/gim, '<li class="ml-4 list-disc">$1</li>')
    .replace(/^\d+\. (.*$)/gim, '<li class="ml-4 list-decimal">$1</li>')
    // 段落
    .replace(/\n\n/g, '</p><p class="my-3">')
    // 换行
    .replace(/\n/g, '<br />');

  return (
    <div
      className={`prose prose-sm md:prose-base dark:prose-invert max-w-none ${className}`}
      dangerouslySetInnerHTML={{ __html: `<p>${html}</p>` }}
    />
  );
}
