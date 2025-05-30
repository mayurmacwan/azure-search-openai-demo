import { useId } from "@fluentui/react-hooks";
import { useTranslation } from "react-i18next";
import { TextField, ITextFieldProps, Checkbox, ICheckboxProps } from "@fluentui/react";
import { HelpCallout } from "../HelpCallout";
import styles from "./Settings.module.css";

// Add type for onRenderLabel
type RenderLabelType = ITextFieldProps | ICheckboxProps;

export interface SettingsProps {
    promptTemplate: string;
    temperature: number;
    seed: number | null;
    className?: string;
    onChange: (field: string, value: any) => void;
    streamingEnabled?: boolean;
    shouldStream?: boolean;
    useSuggestFollowupQuestions?: boolean;
    showSuggestFollowupQuestions?: boolean;
}

export const Settings = ({
    promptTemplate,
    temperature,
    seed,
    className,
    onChange,
    streamingEnabled,
    shouldStream,
    useSuggestFollowupQuestions,
    showSuggestFollowupQuestions
}: SettingsProps) => {
    const { t } = useTranslation();

    // Form field IDs
    const promptTemplateId = useId("promptTemplate");
    const promptTemplateFieldId = useId("promptTemplateField");
    const temperatureId = useId("temperature");
    const temperatureFieldId = useId("temperatureField");
    const seedId = useId("seed");
    const seedFieldId = useId("seedField");
    const shouldStreamId = useId("shouldStream");
    const shouldStreamFieldId = useId("shouldStreamField");
    const suggestFollowupQuestionsId = useId("suggestFollowupQuestions");
    const suggestFollowupQuestionsFieldId = useId("suggestFollowupQuestionsField");

    const renderLabel = (props: RenderLabelType | undefined, labelId: string, fieldId: string, helpText: string) => (
        <HelpCallout labelId={labelId} fieldId={fieldId} helpText={helpText} label={props?.label} />
    );

    return (
        <div className={className}>
            <TextField
                id={promptTemplateFieldId}
                className={styles.settingsSeparator}
                defaultValue={promptTemplate}
                label={t("labels.promptTemplate")}
                multiline
                autoAdjustHeight
                onChange={(_ev, val) => onChange("promptTemplate", val || "")}
                aria-labelledby={promptTemplateId}
                onRenderLabel={props => renderLabel(props, promptTemplateId, promptTemplateFieldId, t("helpTexts.promptTemplate"))}
            />

            <TextField
                id={temperatureFieldId}
                className={styles.settingsSeparator}
                label={t("labels.temperature")}
                type="number"
                min={0}
                max={1}
                step={0.1}
                defaultValue={temperature.toString()}
                onChange={(_ev, val) => onChange("temperature", parseFloat(val || "0"))}
                aria-labelledby={temperatureId}
                onRenderLabel={props => renderLabel(props, temperatureId, temperatureFieldId, t("helpTexts.temperature"))}
            />

            <TextField
                id={seedFieldId}
                className={styles.settingsSeparator}
                label={t("labels.seed")}
                type="text"
                defaultValue={seed?.toString() || ""}
                onChange={(_ev, val) => onChange("seed", val ? parseInt(val) : null)}
                aria-labelledby={seedId}
                onRenderLabel={props => renderLabel(props, seedId, seedFieldId, t("helpTexts.seed"))}
            />

            {streamingEnabled && (
                <Checkbox
                    id={shouldStreamFieldId}
                    className={styles.settingsSeparator}
                    checked={shouldStream}
                    label={t("labels.shouldStream")}
                    onChange={(_ev, checked) => onChange("shouldStream", !!checked)}
                    aria-labelledby={shouldStreamId}
                    onRenderLabel={props => renderLabel(props, shouldStreamId, shouldStreamFieldId, t("helpTexts.shouldStream"))}
                />
            )}

            {showSuggestFollowupQuestions && (
                <Checkbox
                    id={suggestFollowupQuestionsFieldId}
                    className={styles.settingsSeparator}
                    checked={useSuggestFollowupQuestions}
                    label={t("labels.suggestFollowupQuestions")}
                    onChange={(_ev, checked) => onChange("useSuggestFollowupQuestions", !!checked)}
                    aria-labelledby={suggestFollowupQuestionsId}
                    onRenderLabel={props =>
                        renderLabel(props, suggestFollowupQuestionsId, suggestFollowupQuestionsFieldId, t("helpTexts.suggestFollowupQuestions"))
                    }
                />
            )}
        </div>
    );
};
