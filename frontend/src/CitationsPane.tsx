import React from 'react';

interface Citation {
  type: 'web' | 'document';
  title: string;
  url?: string;
}

interface CitationsPaneProps {
  citations: Citation[];
}

const CitationsPane: React.FC<CitationsPaneProps> = ({ citations }) => {
  return (
    <div className="citations-content">
      {citations.length === 0 ? (
        <div className="no-citations">No citations available yet.</div>
      ) : (
        <ul className="citations-list">
          {citations.map((citation, index) => (
            <li key={index} className={`citation-item citation-${citation.type}`}>
              {citation.type === 'web' && citation.url ? (
                <a href={citation.url} target="_blank" rel="noopener noreferrer">
                  {citation.title}
                </a>
              ) : (
                <span>{citation.title}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default CitationsPane;
