import React from 'react';

export const CodePage: React.FC = () => {
  return (
    <div className="h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto py-8 px-4">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">代码编辑器</h1>
        <div className="bg-white rounded-lg shadow p-8">
          <p className="text-gray-600">
            代码编辑器功能开发中...
          </p>
          <p className="text-gray-500 mt-2 text-sm">
            即将支持：Monaco Editor、语法高亮、代码执行、文件保存
          </p>
        </div>
      </div>
    </div>
  );
};
