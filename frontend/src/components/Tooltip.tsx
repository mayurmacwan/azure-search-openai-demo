import React, { useState } from 'react';
import type { ReactNode } from 'react';

interface TooltipProps {
  children: ReactNode;
  text: string;
}

const Tooltip: React.FC<TooltipProps> = ({ children, text }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  
  return (
    <div 
      className="tooltip-container"
      style={{ 
        position: 'relative',
        display: 'inline-block',
      }}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {children}
      
      {showTooltip && (
        <div className="tooltip">
          {text}
        </div>
      )}
    </div>
  );
};

export default Tooltip;
