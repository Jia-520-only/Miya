/**
 * 文化分类详情页面
 * 展示日记、小说、书单、美图库等具体内容
 */

import { useParams } from 'react-router-dom';
import { useState } from 'react';

interface CultureItem {
  id: number;
  title: string;
  content: string;
  date: string;
  tags: string[];
  imageUrl?: string;
  category?: string;
}

const categoryInfo: Record<string, { name: string; icon: string; description: string; color: string }> = {
  diary: {
    name: '生活日记',
    icon: '📔',
    description: '记录生活中的点滴',
    color: 'from-pink-400 to-rose-500'
  },
  novel: {
    name: '原创小说',
    icon: '📖',
    description: '创作的小说故事',
    color: 'from-purple-400 to-indigo-500'
  },
  books: {
    name: '阅读书单',
    icon: '📚',
    description: '推荐好书，分享阅读心得',
    color: 'from-blue-400 to-cyan-500'
  },
  gallery: {
    name: '美图库',
    icon: '🎨',
    description: '收藏的美图',
    color: 'from-green-400 to-emerald-500'
  },
  music: {
    name: '音乐分享',
    icon: '🎵',
    description: '喜欢的音乐和歌单',
    color: 'from-yellow-400 to-amber-500'
  },
  quotes: {
    name: '语录摘抄',
    icon: '💭',
    description: '触动心灵的句子',
    color: 'from-teal-400 to-cyan-500'
  }
};

const sampleDiaries: CultureItem[] = [
  {
    id: 1,
    title: '春日随笔：樱花与咖啡',
    content: '今天下午在樱花树下喝咖啡，微风轻抚，花瓣飘落在杯中，这一刻的美好值得记录。\n\n樱花开了，满树的粉白如云似霞。我坐在树下的木椅上，手捧一杯温热的拿铁，看着花瓣一片片飘落。有的落在我的肩头，有的落在书页上，有的就那样在空中打着转，最后轻柔地落在地上。\n\n想起春天这个词，总觉得带着新生的气息。万物复苏，草木萌发，连空气都变得温柔起来。我写了几行文字，记录下这份心境：\n\n"樱花树下咖啡香，\n微风轻抚花瓣扬。\n一纸素笺心事寄，\n半盏清茶岁月长。"\n\n也许这就是生活吧，平淡中藏着诗意，普通里透着美好。',
    date: '2026-03-07',
    tags: ['心情', '生活', '春天', '樱花']
  },
  {
    id: 2,
    title: '深夜随笔：关于成长的思考',
    content: '深夜无眠，想起这些年的点点滴滴，忽然有些感慨。\n\n成长是什么？是渐渐懂得，是慢慢接受，是学会放下，也是继续坚持。\n\n小时候总想快点长大，觉得长大后就可以自由自在。可真的长大了才发现，原来每个阶段都有每个阶段的烦恼。只是我们学会了更好地面对，学会了用不同的方式处理问题。\n\n有时候会觉得累，觉得生活不易。但转念一想，这何尝不是一种幸运？至少我们还在这条路上，还在努力着，还在为了自己想要的生活而奋斗。\n\n晚安，愿明天会更好。',
    date: '2026-03-05',
    tags: ['心情', '成长', '感悟']
  }
];

const sampleNovels: CultureItem[] = [
  {
    id: 1,
    title: '第一章：初遇',
    content: '那是深秋的傍晚，图书馆的灯光昏黄温暖。她抱着厚厚的书走过，书页在风中翻动，发出沙沙的声响。\n\n我就坐在靠窗的位置，看着夕阳将整个图书馆染成金色。玻璃窗上倒映着她的影子，轻柔得像一缕烟。\n\n"请问，这里有人吗？"她的声音很轻，像是怕打扰了这份宁静。\n\n我摇摇头，她在我对面坐下，将书摊开。我偷偷瞄了一眼书名——《百年孤独》。就这样，我们的故事开始了。\n\n后来的日子里，我们常常在这里相遇。有时候说几句话，有时候只是安静地各自读书。那种默契，像是早就在那里等着我们。',
    date: '2026-03-05',
    tags: ['小说', '原创', '连载', '爱情'],
    category: '长篇连载'
  }
];

const sampleBooks: CultureItem[] = [
  {
    id: 1,
    title: '《百年孤独》读书笔记',
    content: '马尔克斯用诗意的语言编织了一个家族七代人的命运轮回，孤独是永恒的主题。\n\n"多年以后，奥雷连诺上校站在行刑队面前，准会想起父亲带他去参观冰块的那个遥远的下午。"这句开篇，已经成为文学史上最经典的开篇之一。\n\n读完这本书，我一直在想，孤独到底是什么？是布恩迪亚家族每个人都要面对的宿命，还是每个人生命中无法逃避的主题？\n\n也许，孤独并不一定是坏事。它让我们有时间思考，有机会与自己对话，有勇气面对内心最深处的渴望。',
    date: '2026-03-03',
    tags: ['书评', '文学', '经典', '马尔克斯']
  }
];

export default function CultureCategoryPage() {
  const { categoryId } = useParams<{ categoryId: string }>();
  const [selectedItem, setSelectedItem] = useState<CultureItem | null>(null);

  const category = categoryInfo[categoryId || ''] || {
    name: '文化区',
    icon: '✨',
    description: '内容分享',
    color: 'from-purple-400 to-pink-500'
  };

  const getItems = (type: string): CultureItem[] => {
    switch(type) {
      case 'diary': return sampleDiaries;
      case 'novel': return sampleNovels;
      case 'books': return sampleBooks;
      default: return [];
    }
  };

  const items = getItems(categoryId || '');

  return (
    <div className="min-h-screen bg-gradient-to-br from-pink-50 via-purple-50 to-blue-50 dark:from-gray-900 dark:via-purple-900 dark:to-gray-900">
      {/* 页面头部 */}
      <div className={`bg-gradient-to-r ${category.color} text-white py-12`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center space-x-4">
            <div className="text-6xl">{category.icon}</div>
            <div>
              <h1 className="text-4xl font-bold mb-2">{category.name}</h1>
              <p className="text-lg text-white/90">{category.description}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {selectedItem ? (
          /* 详情视图 */
          <div className="max-w-4xl mx-auto">
            <button
              onClick={() => setSelectedItem(null)}
              className="mb-6 text-purple-600 dark:text-purple-400 hover:underline flex items-center"
            >
              <span className="mr-2">←</span>
              返回列表
            </button>
            <article className="bg-white dark:bg-gray-800 rounded-xl p-8 shadow-lg">
              <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">
                {selectedItem.title}
              </h2>
              <div className="flex items-center space-x-4 text-sm text-gray-500 dark:text-gray-400 mb-6">
                <span>{selectedItem.date}</span>
                {selectedItem.category && (
                  <>
                    <span>•</span>
                    <span>{selectedItem.category}</span>
                  </>
                )}
              </div>
              {selectedItem.imageUrl && (
                <img
                  src={selectedItem.imageUrl}
                  alt={selectedItem.title}
                  className="w-full rounded-lg mb-6"
                />
              )}
              <div className="prose dark:prose-invert max-w-none text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-line">
                {selectedItem.content}
              </div>
              <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
                <div className="flex flex-wrap gap-2">
                  {selectedItem.tags.map(tag => (
                    <span
                      key={tag}
                      className="px-3 py-1 bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 rounded-full text-sm"
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              </div>
            </article>
          </div>
        ) : (
          /* 列表视图 */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {items.map((item) => (
              <div
                key={item.id}
                className="bg-white dark:bg-gray-800 rounded-xl overflow-hidden shadow-lg hover:shadow-xl transition-shadow cursor-pointer group"
                onClick={() => setSelectedItem(item)}
              >
                {item.imageUrl && (
                  <div className="h-48 bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center">
                    <span className="text-6xl group-hover:scale-110 transition-transform">🖼️</span>
                  </div>
                )}
                <div className="p-6">
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2 group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                    {item.title}
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                    {item.date}
                  </p>
                  <p className="text-gray-600 dark:text-gray-300 line-clamp-3">
                    {item.content.substring(0, 100)}...
                  </p>
                </div>
              </div>
            ))}

            {items.length === 0 && (
              <div className="col-span-full text-center py-16">
                <div className="text-6xl mb-4">📝</div>
                <p className="text-xl text-gray-600 dark:text-gray-400">
                  暂无内容
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
