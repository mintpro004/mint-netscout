import styles from './ScanBanner.module.css'

export default function ScanBanner({ message }) {
  return (
    <div className={styles.banner}>
      <div className={styles.spinner} />
      <div className={styles.text}>◈ {message || 'DEEP DISCOVERY IN PROGRESS…'}</div>
      <div className={styles.track}><div className={styles.fill} /></div>
    </div>
  )
}
