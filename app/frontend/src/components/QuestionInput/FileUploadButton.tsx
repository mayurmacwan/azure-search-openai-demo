import { ChangeEvent, useRef, useState } from "react";
import { Button, Tooltip } from "@fluentui/react-components";
import { AttachRegular, Attach24Regular } from "@fluentui/react-icons";

import { uploadFileNoAuthApi } from "../../api";
import styles from "./QuestionInput.module.css";

interface Props {
    onUploadComplete?: (message: string) => void;
}

export const FileUploadButton = ({ onUploadComplete }: Props) => {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [retryCount, setRetryCount] = useState(0);

    const handleUploadClick = () => {
        if (fileInputRef.current) {
            fileInputRef.current.click();
        }
    };

    const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) {
            return;
        }

        try {
            setIsUploading(true);
            const file = files[0];

            // Check file size (max 10MB)
            if (file.size > 10 * 1024 * 1024) {
                throw new Error("File size exceeds 10MB limit");
            }

            const formData = new FormData();
            formData.append("file", file);

            if (onUploadComplete) {
                onUploadComplete(`Uploading ${file.name}...`);
            }

            console.log(`Uploading file: ${file.name} (${file.size} bytes)`);
            const response = await uploadFileNoAuthApi(formData);
            console.log("Upload response:", response);

            if (response.status === "warning") {
                // Partial success
                if (onUploadComplete) {
                    onUploadComplete(`${file.name} uploaded, but with a warning: ${response.message}. The file may need manual processing.`);
                }
            } else if (response.status === "success") {
                // Full success
                if (onUploadComplete) {
                    onUploadComplete(
                        `${file.name} uploaded successfully! Document processing has started. ` +
                            `This can take 2-5 minutes before the document is available for questions.`
                    );
                }
            } else {
                // Unknown status
                if (onUploadComplete) {
                    onUploadComplete(`${file.name} uploaded with status: ${response.status}. ${response.message}`);
                }
            }
        } catch (error: any) {
            console.error("Error uploading file:", error);

            // If the error is a network error, we might want to retry
            if (error.message?.includes("NetworkError") || error.message?.includes("Failed to fetch")) {
                if (retryCount < 2) {
                    // Limit to 2 retries
                    setRetryCount(retryCount + 1);
                    if (onUploadComplete) {
                        onUploadComplete(`Network error during upload. Retrying (${retryCount + 1}/3)...`);
                    }
                    // Queue a retry after a short delay
                    setTimeout(() => {
                        if (fileInputRef.current && fileInputRef.current.files && fileInputRef.current.files.length > 0) {
                            handleFileChange(e);
                        }
                    }, 2000);
                    return;
                }
            }

            const errorMessage = error.message || "Error uploading file. Please try again.";
            if (onUploadComplete) {
                onUploadComplete(`Error: ${errorMessage}`);
            }
        } finally {
            setIsUploading(false);
            // Reset retry count
            setRetryCount(0);
            // Reset the file input so the same file can be uploaded again if needed
            if (fileInputRef.current) {
                fileInputRef.current.value = "";
            }
        }
    };

    return (
        <div className={styles.questionInputButtonsContainer}>
            <input
                type="file"
                ref={fileInputRef}
                style={{ display: "none" }}
                onChange={handleFileChange}
                accept=".txt, .md, .json, .png, .jpg, .jpeg, .bmp, .heic, .tiff, .pdf, .docx, .xlsx, .pptx, .html"
            />
            <Tooltip content="Upload Document" relationship="label">
                <Button
                    size="large"
                    icon={<Attach24Regular primaryFill={isUploading ? "rgba(173, 173, 173, 0.8)" : "rgba(115, 118, 225, 1)"} />}
                    onClick={handleUploadClick}
                    disabled={isUploading}
                    aria-label="Upload Document"
                />
            </Tooltip>
        </div>
    );
};
