import { Stack } from "@fluentui/react";
import { animated, useSpring } from "@react-spring/web";
import { Sparkle28Filled } from "@fluentui/react-icons";

const AnswerIcon: React.FC = () => {
  return <Sparkle28Filled primaryFill={"rgba(115, 118, 225, 1)"} aria-hidden="true" aria-label="Answer logo" />;
};

export const AnswerLoading: React.FC = () => {
  const animatedStyles = useSpring({
    from: { opacity: 0 },
    to: { opacity: 1 }
  });

    return (
      <div className={`message-bubble ai`}>
        <animated.div style={{ ...animatedStyles }}>
          <Stack className={'loading-container'} verticalAlign="space-between">
            <AnswerIcon />
            <Stack.Item grow>
              <p className={'loading-text'}>
                Generating answer
                <span className={'loading-dots'} />
              </p>
            </Stack.Item>
          </Stack>
        </animated.div>
      </div>
    );
};