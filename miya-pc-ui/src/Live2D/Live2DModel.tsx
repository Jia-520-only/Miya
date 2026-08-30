import React, { useRef, useEffect, useState } from 'react';
import { Application } from 'pixi.js';
import { Live2DModel as Live2DModelPixi } from '@pixi-live2d-display/pixi-live2d-display';

interface Live2DModelProps {
  modelPath: string;
  emotion: string;
  scale?: number;
}

export const Live2DModel: React.FC<Live2DModelProps> = ({
  modelPath,
  emotion,
  scale = 1,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const modelRef = useRef<Live2DModel | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    const init = async () => {
      try {
        const app = new Application();
        await app.init({ resizeTo: containerRef.current });
        containerRef.current.appendChild(app.canvas);
        appRef.current = app;

        const model = await Live2DModelPixi.from(modelPath);
        model.scale.set(scale);
        app.stage.addChild(model);
        modelRef.current = model;

        setLoaded(true);
      } catch (error) {
        console.error('Failed to load Live2D model:', error);
      }
    };

    init();

    return () => {
      if (appRef.current) {
        appRef.current.destroy(true);
      }
    };
  }, [modelPath, scale]);

  useEffect(() => {
    if (!modelRef.current || !loaded) return;

    const expressionMap: Record<string, string> = {
      happiness: 'f01',
      sadness: 'f02',
      anger: 'f03',
      fear: 'f04',
      surprise: 'f05',
      calm: 'f00',
    };

    const expression = expressionMap[emotion] || 'f00';
    modelRef.current.internalModel.motionManager.expressionManager.setExpression(
      expression
    );
  }, [emotion, loaded]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full"
      style={{ cursor: 'grab' }}
    />
  );
};
