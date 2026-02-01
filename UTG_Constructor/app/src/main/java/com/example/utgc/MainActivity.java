package com.example.utgc;

import android.annotation.TargetApi;
import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.IBinder;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.View;
import android.widget.EditText;
import android.widget.TextView;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.app.ActivityCompat;
import java.io.File;
import java.util.Objects;

import com.example.utgc.ScreenCaptureImageActivity;
import com.example.utgc.ForeGroundService;
import android.content.SharedPreferences;

///storage/emulated/0/Android/data/com.example.utgc/files/UIdata/com.mtr.mtrmobile/
public class MainActivity extends AppCompatActivity {

    private static final String TAG = MainActivity.class.getName();
    public static int ACTION_MANAGE_OVERLAY_PERMISSION_REQUEST_CODE= 5469;
    public static DisplayMetrics display_metrics;

    private EditText packText=null;
    private EditText startClassText=null;
    private String packString;
    private String classString;
    private String externalDir;
    private String appDir;
    private TextView rootPathTextView;
    private TextView startActivityTextView;

    Intent mqttIntent = null;
    boolean isServiceConnected = false;

    private MyBroadcastReceiver myReceiver;

    public class MyBroadcastReceiver extends BroadcastReceiver {
        @Override
        public void onReceive(Context context, Intent intent) {
            // 当接收到特定的广播时，关闭应用
            closeApplication();
        }
    }

    private final ServiceConnection connection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder service) {
            MQTTHelper.getInstance().setMyBinder((MQTTService.MyBinder) service);
            isServiceConnected = true;
            Log.e("Main","服务已连接");
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            isServiceConnected = false;
            MQTTHelper.getInstance().setMyBinder(null);
        }
    };
    @TargetApi(23)
    public void testOverlayPermission() {
        if (!Settings.canDrawOverlays(this)) {
            Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName()));
            startActivityForResult(intent, ACTION_MANAGE_OVERLAY_PERMISSION_REQUEST_CODE);
        }
    }

    @TargetApi(23)
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == ACTION_MANAGE_OVERLAY_PERMISSION_REQUEST_CODE) {
            if (Settings.canDrawOverlays(this)) {
                System.out.println("WowICan");
            }
        } else {
            System.out.println("Intent");
            display_metrics = new DisplayMetrics();

            final Context context = this;
            final View upper_view = new View(context);
            final View bottom_view = new View(context);

        }
    }

    private static final int REQUEST_EXTERNAL_STORAGE = 1;
    private static String[] PERMISSIONS_STORAGE = {
            "android.permission.READ_EXTERNAL_STORAGE",
            "android.permission.WRITE_EXTERNAL_STORAGE" };


    public static void verifyStoragePermissions(Activity activity) {
        try {
            //检测是否有写的权限
            int permission = ActivityCompat.checkSelfPermission(activity,
                    "android.permission.WRITE_EXTERNAL_STORAGE");
            if (permission != PackageManager.PERMISSION_GRANTED) {
                // 没有写的权限，去申请写的权限，会弹出对话框
                ActivityCompat.requestPermissions(activity, PERMISSIONS_STORAGE,REQUEST_EXTERNAL_STORAGE);
            }
        } catch (Exception e) {
            e.printStackTrace();
            //CrashReport.postCatchedException(e);
        }
    }
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        //this.setVolumeControlStream(AudioManager.STREAM_MUSIC);
        verifyStoragePermissions(this);
        // SophixManager.getInstance().queryAndLoadNewPatch();
        setContentView(R.layout.activity_main);

        File externalFilesDir = getExternalFilesDir(null);
        if (externalFilesDir != null)
        {
            externalDir = externalFilesDir.getAbsolutePath() + "/UIdata/";

        }

        packText = (EditText) this.findViewById(R.id.packName);
        startClassText = (EditText) this.findViewById(R.id.className);
        rootPathTextView = ((TextView) this.findViewById(R.id.rootPath));
        rootPathTextView.setText(externalDir);
        startActivityTextView = ((TextView) this.findViewById(R.id.actActivity));


        if (Build.VERSION.SDK_INT >= 23){
            testOverlayPermission();
        }

        //在外部存储环境就绪的情况下，存储用户输入的要收集的app的包名和类名，并创建和记录该app的数据所要保存的目录地址(appDir)
        findViewById(R.id.set).setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View arg0) {
                if (externalDir != null)
                {
                    packString = packText.getText().toString();
                    classString = startClassText.getText().toString();

                    appDir = externalDir+ packString+"/";
                    rootPathTextView.setText(appDir);
                    File directory = new File(appDir);
                    if (!directory.exists()) {
                        // If the directory does not exist, create it
                        boolean isDirectoryCreated = directory.mkdirs();
                        Log.d(TAG, "root directory for the app: "+ packString+"has been created");
                    }


                    SharedPreferences sharedPref = getSharedPreferences("Data", MODE_PRIVATE);
                    SharedPreferences.Editor editor = sharedPref.edit();
                    editor.putString("package", packString);
                    editor.putString("startClass", classString);
                    editor.putString("collectAppDir", appDir);
                    editor.apply();
                    startActivityTextView.setText(packString+"/"+classString);
                }
            }
        });

        //点击start construction按钮，启动前台服务并运行截图activity
        this.findViewById(R.id.start).setOnClickListener(new View.OnClickListener() {
            //此处需要一个点击停止foregroundservice的处理，暂时还没写
            @Override
            public void onClick(View arg0) {

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    Intent intent = new Intent(MainActivity.this, ForeGroundService.class);
                    startForegroundService(intent);
                } else {
                    Intent intent = new Intent(MainActivity.this, ForeGroundService.class);
                    startService(intent);
                }

            }
        });

        this.findViewById(R.id.settings).setOnClickListener(new View.OnClickListener() {

            @Override
            public void onClick(View arg0) {
                startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
            }
        });

        mqttIntent = new Intent(MainActivity.this,MQTTService.class);
        bindService(mqttIntent,connection,BIND_AUTO_CREATE);
        stopService(mqttIntent);
        startService(mqttIntent);

        // 注册广播接收器
        myReceiver = new MyBroadcastReceiver();
        IntentFilter filter = new IntentFilter("com.example.CLOSE_APP");
        registerReceiver(myReceiver, filter);

    }

    protected void onDestroy() {
        super.onDestroy();
        // 取消注册广播接收器
        unregisterReceiver(myReceiver);
    }

    public void closeApplication() {
        finishAffinity();
        System.exit(0);
    }

    @Override
    protected void onResume() {
        super.onResume();

        File externalFilesDir = getExternalFilesDir(null);
        if (externalFilesDir != null)
        {
            externalDir = externalFilesDir.getAbsolutePath() + "/UIdata/";
        }

        packText = (EditText) this.findViewById(R.id.packName);
        startClassText = (EditText) this.findViewById(R.id.className);
        rootPathTextView = ((TextView) this.findViewById(R.id.rootPath));
        rootPathTextView.setText(externalDir);
        startActivityTextView = ((TextView) this.findViewById(R.id.actActivity));

        packString = packText.getText().toString();
        classString = startClassText.getText().toString();

        if (Build.VERSION.SDK_INT >= 23){
            testOverlayPermission();
        }

        //在外部存储环境就绪的情况下，存储用户输入的要收集的app的包名和类名，并记录该app的数据所要保存的目录地址(appDir)
        this.findViewById(R.id.set).setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View arg0) {
                if (externalDir != null)
                {
                    packString = packText.getText().toString();
                    classString = startClassText.getText().toString();

                    appDir = externalDir+ packString+"/";
                    rootPathTextView.setText(appDir);

                    File directory = new File(appDir);
                    if (!directory.exists()) {
                        // If the directory does not exist, create it
                        directory.mkdirs();
                        Log.d(TAG, "root directory for the app: "+ packString+"has been created");
                    }

                    SharedPreferences sharedPref = getSharedPreferences("Data", MODE_PRIVATE);
                    SharedPreferences.Editor editor = sharedPref.edit();
                    editor.putString("package", packString);
                    editor.putString("startClass", classString);
                    editor.putString("collectAppDir", appDir);
                    editor.apply();

                    startActivityTextView.setText(packString+"/"+classString);
                }
                //setSharedPreferenceData("", );
            }
        });

        //点击start construction按钮，启动前台服务并运行截图activity
        this.findViewById(R.id.start).setOnClickListener(new View.OnClickListener() {
            //此处需要一个点击停止foregroundservice的处理，暂时还没写
            @Override
            public void onClick(View arg0) {

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    Intent intent = new Intent(MainActivity.this, ForeGroundService.class);
                    startForegroundService(intent);
                } else {
                    Intent intent = new Intent(MainActivity.this, ForeGroundService.class);
                    startService(intent);
                }

            }
        });

        this.findViewById(R.id.settings).setOnClickListener(new View.OnClickListener() {

            @Override
            public void onClick(View arg0) {
                startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
            }
        });
    }



    /*
    public void setSharedPreferenceData(String Name, String dataStr) {
        SharedPreferences sharedPref = getSharedPreferences("Data", MODE_PRIVATE);
        SharedPreferences.Editor editor = sharedPref.edit();
        editor.putString(Name, dataStr);
        editor.apply();
    }

    public String getSharedPreferenceData(String Name) {
        SharedPreferences sharedPref = getSharedPreferences("Data", MODE_PRIVATE);
        return sharedPref.getString(Name, null);
    }
    */


}