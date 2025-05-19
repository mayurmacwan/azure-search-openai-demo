import { Stack, Pivot, PivotItem, IconButton } from "@fluentui/react";
import { useTranslation } from "react-i18next";
import styles from "./AnalysisPanel.module.css";
import chatStyles from "../../pages/chat/Chat.module.css";

import { SupportingContent } from "../SupportingContent";
import { ChatAppResponse } from "../../api";
import { AnalysisPanelTabs } from "./AnalysisPanelTabs";
import { ThoughtProcess } from "./ThoughtProcess";
import { MarkdownViewer } from "../MarkdownViewer";
import { useMsal } from "@azure/msal-react";
import { getHeaders } from "../../api";
import { useLogin, getToken } from "../../authConfig";
import { useState, useEffect, useRef } from "react";

interface Props {
    className: string;
    activeTab: AnalysisPanelTabs;
    onActiveTabChanged: (tab: AnalysisPanelTabs) => void;
    activeCitation: string | undefined;
    citationHeight: string;
    answer: ChatAppResponse;
}

const pivotItemDisabledStyle = { disabled: true, style: { color: "grey" } };

export const AnalysisPanel = ({ answer, activeTab, activeCitation, citationHeight, className, onActiveTabChanged }: Props) => {
    const isDisabledThoughtProcessTab: boolean = !answer.context.thoughts;
    const isDisabledSupportingContentTab: boolean = !answer.context.data_points;
    const isDisabledCitationTab: boolean = !activeCitation;
    const [citation, setCitation] = useState("");
    const [isExpanded, setIsExpanded] = useState(false);
    const [startX, setStartX] = useState(0);
    const [startWidth, setStartWidth] = useState(0);
    const [isDragging, setIsDragging] = useState(false);
    const panelRef = useRef<HTMLDivElement>(null);

    const client = useLogin ? useMsal().instance : undefined;
    const { t } = useTranslation();

    const fetchCitation = async () => {
        const token = client ? await getToken(client) : undefined;
        if (activeCitation) {
            // Get hash from the URL as it may contain #page=N
            // which helps browser PDF renderer jump to correct page N
            const originalHash = activeCitation.indexOf("#") ? activeCitation.split("#")[1] : "";
            const response = await fetch(activeCitation, {
                method: "GET",
                headers: await getHeaders(token)
            });
            const citationContent = await response.blob();
            let citationObjectUrl = URL.createObjectURL(citationContent);
            // Add hash back to the new blob URL
            if (originalHash) {
                citationObjectUrl += "#" + originalHash;
            }
            setCitation(citationObjectUrl);
        }
    };

    useEffect(() => {
        fetchCitation();

        // Set to expanded view when citation tab is active
        if (activeTab === AnalysisPanelTabs.CitationTab && !isExpanded) {
            setIsExpanded(true);
        }
    }, [activeTab, activeCitation]);

    const toggleExpand = () => {
        setIsExpanded(!isExpanded);
    };

    const handleMouseDown = (e: React.MouseEvent) => {
        setStartX(e.clientX);
        if (panelRef.current) {
            setStartWidth(panelRef.current.offsetWidth);
        }
        setIsDragging(true);
    };

    const handleMouseMove = (e: MouseEvent) => {
        if (!isDragging) return;

        const diff = startX - e.clientX;
        if (panelRef.current) {
            const newWidth = Math.min(Math.max(startWidth + diff, 350), window.innerWidth * 0.7);
            panelRef.current.style.width = `${newWidth}px`;
        }
    };

    const handleMouseUp = () => {
        setIsDragging(false);
    };

    useEffect(() => {
        if (isDragging) {
            document.addEventListener("mousemove", handleMouseMove);
            document.addEventListener("mouseup", handleMouseUp);
        } else {
            document.removeEventListener("mousemove", handleMouseMove);
            document.removeEventListener("mouseup", handleMouseUp);
        }

        return () => {
            document.removeEventListener("mousemove", handleMouseMove);
            document.removeEventListener("mouseup", handleMouseUp);
        };
    }, [isDragging, startX, startWidth]);

    const renderFileViewer = () => {
        if (!activeCitation) {
            return null;
        }

        const fileExtension = activeCitation.split(".").pop()?.toLowerCase();
        switch (fileExtension) {
            case "png":
            case "jpg":
            case "jpeg":
            case "gif":
                return <img src={citation} className={styles.citationImg} alt="Citation Image" />;
            case "md":
                return <MarkdownViewer src={activeCitation} />;
            case "pdf":
                return (
                    <div className={styles.citationPdfContainer}>
                        <iframe title="Citation PDF" src={citation} className={`${styles.citationPdf} ${isExpanded ? styles.fullHeightCitation : ""}`} />
                    </div>
                );
            default:
                return <iframe title="Citation" src={citation} width="100%" height={isExpanded ? "calc(100vh - 100px)" : citationHeight} />;
        }
    };

    return (
        <div ref={panelRef} className={`${className} ${isExpanded ? chatStyles.panelExpanded : ""}`}>
            <div className={chatStyles.panelResizeHandle} onMouseDown={handleMouseDown}></div>

            <div className={chatStyles.panelControls}>
                <button className={chatStyles.panelControlButton} onClick={toggleExpand} title={isExpanded ? "Collapse panel" : "Expand panel"}>
                    {isExpanded ? "↔" : "⇔"}
                </button>
            </div>

            <Pivot selectedKey={activeTab} onLinkClick={pivotItem => pivotItem && onActiveTabChanged(pivotItem.props.itemKey! as AnalysisPanelTabs)}>
                <PivotItem
                    itemKey={AnalysisPanelTabs.ThoughtProcessTab}
                    headerText={t("headerTexts.thoughtProcess")}
                    headerButtonProps={isDisabledThoughtProcessTab ? pivotItemDisabledStyle : undefined}
                >
                    <ThoughtProcess thoughts={answer.context.thoughts || []} />
                </PivotItem>
                <PivotItem
                    itemKey={AnalysisPanelTabs.SupportingContentTab}
                    headerText={t("headerTexts.supportingContent")}
                    headerButtonProps={isDisabledSupportingContentTab ? pivotItemDisabledStyle : undefined}
                >
                    <SupportingContent supportingContent={answer.context.data_points} />
                </PivotItem>
                <PivotItem
                    itemKey={AnalysisPanelTabs.CitationTab}
                    headerText={t("headerTexts.citation")}
                    headerButtonProps={isDisabledCitationTab ? pivotItemDisabledStyle : undefined}
                >
                    {renderFileViewer()}
                </PivotItem>
            </Pivot>
        </div>
    );
};
