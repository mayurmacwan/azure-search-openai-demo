import React, { useState, useEffect, useRef, RefObject } from "react";
import { Outlet, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import styles from "./Layout.module.css";

import { useLogin } from "../../authConfig";
import { LoginButton } from "../../components/LoginButton";
import { Chat24Regular, Settings24Regular, AddSquare24Regular } from "@fluentui/react-icons";
import { useChatContext } from "../../chatContext";

const Layout = () => {
    const { t } = useTranslation();
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef: RefObject<HTMLDivElement> = useRef(null);
    const { resetChat } = useChatContext();

    const handleClickOutside = (event: MouseEvent) => {
        if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
            setMenuOpen(false);
        }
    };

    useEffect(() => {
        if (menuOpen) {
            document.addEventListener("mousedown", handleClickOutside);
        } else {
            document.removeEventListener("mousedown", handleClickOutside);
        }
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [menuOpen]);

    return (
        <div className={styles.layout}>
            {/* Original header - now hidden via CSS */}
            <header className={styles.header} role={"banner"}>
                <div className={styles.headerContainer} ref={menuRef}>
                    <Link to="/" className={styles.headerTitleContainer}>
                        <h3 className={styles.headerTitle}>{t("headerTitle")}</h3>
                    </Link>
                    <div className={styles.loginMenuContainer}>{useLogin && <LoginButton />}</div>
                </div>
            </header>

            {/* New layout with sidebar */}
            <div className={styles.mainContainer}>
                <div className={styles.sidebar}>
                    <div className={styles.sidebarHeader}>
                        <div className={styles.sidebarLogo}>QR</div>
                        <div className={styles.sidebarTitle}>{t("headerTitle")}</div>
                    </div>

                    <button 
                        className={styles.newChatButton}
                        onClick={() => {
                            // Call the resetChat function from context
                            resetChat();
                        }}
                    >
                        <AddSquare24Regular className={styles.newChatIcon} />
                        New Chat
                    </button>

                    <div className={styles.recentChatsHeader}>RECENT CHATS</div>
                    <ul className={styles.chatList}>
                        <li className={styles.chatItem}>
                            <Chat24Regular className={styles.chatItemIcon} />
                            <span className={styles.chatItemText}>New Conversation</span>
                        </li>
                    </ul>

                    <div className={styles.sidebarFooter}>
                        <div className={styles.footerItem}>
                            <Settings24Regular className={styles.footerItemIcon} />
                            <span className={styles.footerItemText}>Settings</span>
                        </div>
                    </div>
                </div>

                <div className={styles.content}>
                    <Outlet />
                </div>
            </div>
        </div>
    );
};

export default Layout;
