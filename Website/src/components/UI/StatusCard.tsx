import "../../styles/statusCard.css";

interface StatusCardProps {
    title: string;
    value: string | number;
    unit?: string;
}

export default function StatusCard({ title, value, unit }: StatusCardProps) {
    return (
        <div className="status-card">
            <h3>{title}</h3>
            <p className="value">
                {value}
                {unit && <span className="unit">{unit}</span>}
            </p>
        </div>
    );
}
