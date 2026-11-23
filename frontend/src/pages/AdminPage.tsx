import AreaPlaceholder from '../components/common/AreaPlaceholder'

export default function AdminPage() {
  return (
    <AreaPlaceholder
      eyebrow="Support head dashboard"
      title="Team overview"
      description="A dashboard for support leadership to review performance metrics and system configuration."
      action={{ href: '/support', label: 'Open support ticket queue' }}
    />
  )
}
