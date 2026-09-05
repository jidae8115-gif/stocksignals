# 조용한시간(23:00~06:00) 동안 큐잉된 텔레그램 알림을 06:00에 일괄 발송
import common as c

if __name__ == "__main__":
    c.flush_pending()
    print("pending_notifications.json flush 완료")
