package com.example.utgc;

import static android.content.Intent.FLAG_ACTIVITY_NEW_TASK;

import android.annotation.SuppressLint;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

public class ForeGroundService extends Service {

    private static final int NOTIFICATION_ID = 1;
    private static final String CHANNEL_ID = "ForegroundServiceChannel";
    private static final String TAG = ForeGroundService.class.getName();


    public ForeGroundService() {
    }

    @SuppressLint("ForegroundServiceType")
    @Override
    public void onCreate() {
        super.onCreate();
        //Notification notification = createNotification();
        //startForeground(NOTIFICATION_ID, notification);

        //Intent intent = new Intent(this, ScreenCaptureImageActivity.class);
        //intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        //this.startActivity(intent);

    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Notification notification = createNotification();
        startForeground(NOTIFICATION_ID, notification);

        Intent intentScreenCap = new Intent(this, ScreenCaptureImageActivity.class);
        intentScreenCap.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        this.startActivity(intentScreenCap);
        return super.onStartCommand(intent, flags, startId);
    }

    private Notification createNotification() {
        // Create a notification channel for Android Oreo and above
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(CHANNEL_ID, "Foreground Service Channel", NotificationManager.IMPORTANCE_HIGH);
            NotificationManager notificationManager = getSystemService(NotificationManager.class);
            notificationManager.createNotificationChannel(channel);
        }

        // Create a notification for the foreground service
        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_launcher_foreground)
                .setContentTitle("Foreground Service")
                .setContentText("This is a foreground service running in the background.")
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_SERVICE);

        return builder.build();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        // Return null because this service does not provide binding
        Log.d(TAG,"start foreground service");
        //Intent intentScreenCap = new Intent(this, ScreenCaptureImageActivity.class);
        //startActivity(intentScreenCap);
        return null;
    }
}