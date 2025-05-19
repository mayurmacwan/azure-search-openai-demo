import { useMemo, useState } from "react";
import { Stack, IconButton } from "@fluentui/react";
import { useTranslation } from "react-i18next";
import DOMPurify from "dompurify";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

import styles from "./Answer.module.css";
import { ChatAppResponse, getCitationFilePath, SpeechConfig } from "../../api";
import { parseAnswerToHtml } from "./AnswerParser";
import { SpeechOutputBrowser } from "./SpeechOutputBrowser";
import { SpeechOutputAzure } from "./SpeechOutputAzure";

interface Props {
    answer: ChatAppResponse;
    index: number;
    speechConfig: SpeechConfig;
    isSelected?: boolean;
    isStreaming: boolean;
    onCitationClicked: (filePath: string) => void;
    onThoughtProcessClicked: () => void;
    onSupportingContentClicked: () => void;
    onFollowupQuestionClicked?: (question: string) => void;
    showFollowupQuestions?: boolean;
    showSpeechOutputBrowser?: boolean;
    showSpeechOutputAzure?: boolean;
}

export const Answer = ({
    answer,
    index,
    speechConfig,
    isSelected,
    isStreaming,
    onCitationClicked,
    onThoughtProcessClicked,
    onSupportingContentClicked,
    onFollowupQuestionClicked,
    showFollowupQuestions,
    showSpeechOutputAzure,
    showSpeechOutputBrowser
}: Props) => {
    const followupQuestions = answer.context?.followup_questions;
    const parsedAnswer = useMemo(() => parseAnswerToHtml(answer, isStreaming, onCitationClicked), [answer]);
    const { t } = useTranslation();
    const sanitizedAnswerHtml = DOMPurify.sanitize(parsedAnswer.answerHtml);
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        // Single replace to remove all HTML tags to remove the citations
        const textToCopy = sanitizedAnswerHtml.replace(/<a [^>]*><sup>\d+<\/sup><\/a>|<[^>]+>/g, "");

        navigator.clipboard
            .writeText(textToCopy)
            .then(() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            })
            .catch(err => console.error("Failed to copy text: ", err));
    };

    return (
        <div className={`${styles.answerContainer} ${isSelected && styles.selected}`}>
            <div className={styles.answerAvatar}>QR</div>
            <div className={styles.answerBubble}>
                <div className={styles.answerText}>
                    <ReactMarkdown children={sanitizedAnswerHtml} rehypePlugins={[rehypeRaw]} remarkPlugins={[remarkGfm]} />
                </div>

                {!!parsedAnswer.citations.length && (
                    <div className={styles.citationSection}>
                        <span className={styles.citationLearnMore}>{t("citationWithColon")}</span>
                        <div className={styles.citationsContainer}>
                            {parsedAnswer.citations.map((x, i) => {
                                const path = getCitationFilePath(x);
                                return (
                                    <a key={i} className={styles.citation} title={x} onClick={() => onCitationClicked(path)}>
                                        {`${++i}. ${x.split("/").pop()}`}
                                    </a>
                                );
                            })}
                        </div>
                    </div>
                )}

                {!!followupQuestions?.length && showFollowupQuestions && onFollowupQuestionClicked && (
                    <div className={styles.followupSection}>
                        <span className={styles.followupQuestionLearnMore}>{t("followupQuestions")}</span>
                        <div className={styles.followupQuestionsList}>
                            {followupQuestions.map((x, i) => (
                                <a key={i} className={styles.followupQuestion} title={x} onClick={() => onFollowupQuestionClicked(x)}>
                                    {x}
                                </a>
                            ))}
                        </div>
                    </div>
                )}

                <div className={styles.messageToolbar}>
                    <IconButton
                        className={styles.messageToolbarButton}
                        iconProps={{ iconName: copied ? "CheckMark" : "Copy" }}
                        title={copied ? t("tooltips.copied") : t("tooltips.copy")}
                        ariaLabel={copied ? t("tooltips.copied") : t("tooltips.copy")}
                        onClick={handleCopy}
                    />
                    <IconButton
                        className={styles.messageToolbarButton}
                        iconProps={{ iconName: "Lightbulb" }}
                        title={t("tooltips.showThoughtProcess")}
                        ariaLabel={t("tooltips.showThoughtProcess")}
                        onClick={() => onThoughtProcessClicked()}
                        disabled={!answer.context.thoughts?.length}
                    />
                    <IconButton
                        className={styles.messageToolbarButton}
                        iconProps={{ iconName: "ClipboardList" }}
                        title={t("tooltips.showSupportingContent")}
                        ariaLabel={t("tooltips.showSupportingContent")}
                        onClick={() => onSupportingContentClicked()}
                        disabled={!answer.context.data_points}
                    />
                    {showSpeechOutputAzure && (
                        <SpeechOutputAzure answer={sanitizedAnswerHtml} index={index} speechConfig={speechConfig} isStreaming={isStreaming} />
                    )}
                    {showSpeechOutputBrowser && <SpeechOutputBrowser answer={sanitizedAnswerHtml} />}
                </div>
            </div>
        </div>
    );
};
