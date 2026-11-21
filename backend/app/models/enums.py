from enum import Enum


class UserRole(str, Enum):
    MEMBER = "MEMBER"
    SUPPORT_AGENT = "SUPPORT_AGENT"
    SUPPORT_HEAD = "SUPPORT_HEAD"
    SYSTEM = "SYSTEM"


class TicketCategory(str, Enum):
    PAYMENT = "PAYMENT"
    PROFILE_CHANGE = "PROFILE_CHANGE"
    SURVEY_ISSUE = "SURVEY_ISSUE"
    ELIGIBILITY = "ELIGIBILITY"
    OTHER = "OTHER"


class TicketPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"
    ESCALATED = "ESCALATED"
