// Live2D 表情控制诊断脚本
// 在浏览器控制台中运行此脚本

console.log('=== Live2D 诊断开始 ===\n');

// 1. 获取模型
const canvas = document.querySelector('canvas[data-v-ff201d31]');
if (!canvas) {
  console.error('❌ 未找到 Live2D canvas');
} else {
  console.log('✅ 找到 canvas');

  const app = canvas.__pixi_app;
  if (!app) {
    console.error('❌ PIXI app 未找到');
  } else {
    console.log('✅ PIXI app 已找到');

    const model = app.stage?.children?.[0];
    if (!model) {
      console.error('❌ Live2D 模型未找到');
    } else {
      console.log('✅ Live2D 模型已找到');

      // 2. 检查模型内部结构
      const internal = model.internalModel;
      if (!internal) {
        console.error('❌ internalModel 未找到');
      } else {
        console.log('\n=== 模型内部结构 ===');
        console.log('internalModel:', !!internal);
        console.log('motionManager:', !!internal.motionManager);
        console.log('expressionManager:', !!internal.motionManager?.expressionManager);

        const exprManager = internal.motionManager?.expressionManager;
        if (exprManager) {
          console.log('\n=== ExpressionManager 信息 ===');
          console.log('setExpression 函数:', typeof exprManager.setExpression);
          console.log('expressions 数组:', exprManager.expressions);
          console.log('expressions 长度:', exprManager.expressions?.length || 0);

          if (exprManager.expressions && exprManager.expressions.length > 0) {
            console.log('\n=== 可用表情列表 ===');
            exprManager.expressions.forEach((expr, idx) => {
              console.log(`表情 ${idx}:`, {
                id: expr.id,
                name: expr.name,
                type: typeof expr
              });
            });
          }
        }

        // 3. 尝试设置表情
        console.log('\n=== 测试表情设置 ===');
        if (exprManager && exprManager.expressions && exprManager.expressions.length > 0) {
          const testIndices = [0, 1, 2];

          testIndices.forEach((idx) => {
            console.log(`\n尝试设置表情 ${idx}...`);

            try {
              // 方法1: 使用索引
              exprManager.setExpression(idx);
              console.log(`✅ 方法1 (索引 ${idx}): 成功`);
            } catch (err) {
              console.log(`❌ 方法1 (索引 ${idx}) 失败:`, err.message);

              // 方法2: 使用名称
              const exprName = exprManager.expressions[idx]?.name || exprManager.expressions[idx]?.id;
              if (exprName) {
                try {
                  exprManager.setExpression(exprName);
                  console.log(`✅ 方法2 (名称 "${exprName}"): 成功`);
                } catch (err2) {
                  console.log(`❌ 方法2 (名称 "${exprName}") 失败:`, err2.message);
                }
              }
            }

            // 等待一下再测试下一个
            console.log('等待 1 秒...');
          });

          console.log('\n=== 测试完成 ===');
          console.log('提示: 如果表情设置成功但看不到变化，可能是因为：');
          console.log('1. 表情参数变化不明显');
          console.log('2. 需要更多时间才能看到效果');
          console.log('3. 模型参数定义有问题');
          console.log('4. 表情文件内容不正确');

          // 4. 查看当前参数值
          console.log('\n=== 当前模型参数 ===');
          if (internal.coreModel && typeof internal.coreModel.getParameterValue === 'function') {
            const params = [
              'Param2', 'Param4', 'Param3', 'Param6', 'Param', 'Param7', 'Param8'
            ];
            params.forEach(paramId => {
              const value = internal.coreModel.getParameterValue(paramId);
              console.log(`${paramId}:`, value);
            });
          }
        } else {
          console.log('❌ 没有可用的表情');
        }
      }
    }
  }
}

console.log('\n=== Live2D 诊断结束 ===');
