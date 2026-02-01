package com.example.utgc;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.graphics.Point;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.Display;
import android.view.KeyEvent;
import android.view.OrientationEventListener;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.ByteBuffer;

//adb -s 625a2f23 shell dumpsys activity
//adb -s U45TGA49GM7H6SV8 shell dumpsys package com.ximalaya.ting.android
//com.mtr.mtrmobile/com.mtr.mtrmobile.MTRMobileActivity
//com.openrice.android/com.openrice.android.ui.activity.splashscreen.SplashScreenActivity
//com.deliveroo.orderapp/com.deliveroo.orderapp.splash.feature.SplashActivity
//com.sankuai.sailor.afooddelivery/com.sankuai.sailor.shell.SplashActivity
//com.global.foodpanda.android/com.deliveryhero.applaunch.launcher.LauncherActivity
//ctrip.english/com.ctrip.ibu.myctrip.main.module.home.IBUHomeActivity
//ctrip.android.view/ctrip.business.planthome.CtripPlantHomeActivity
//ctrip.android.view/ctrip.business.splash.CtripSplashActivity
//com.lucky.luckyclient/com.luckin.client.main.FirstActivity
//hk.ust.student/hk.ust.student.MainActivity/com.hkust.MainActivity
//cn.kidyn.qdmedical160/.activity.SchemeEntryActivity
//com.Qunar/com.mqunar.splash.SplashActivity
//com.starbucks.cn/.home.revamp.launch.RevampLaunchActivity
//com.starbucks.cn/.baselib.deeplink.DeeplinkActivity
//cn.damai/.launcher.splash.SplashMainActivity
//com.founder.bysypatientapp/com.founder.bysypatientapp.MainActivity
//com.zuzuChe/.feature.home.launch.SplashActivity
//com.dianping.v1/.NovaMainActivity
//com.yek.android.kfc.activitys/com.yum.brandkfc.SplashAct
//com.anjuke.android.app/.mainmodule.WelcomeActivity
//com.usthing.android/.MainActivity
//com.sdu.didi.psnger/com.didi.sdk.app.MainActivity
//com.ximalaya.ting.android/.host.activity.MainActivity
//com.baidu.homework/com.baidu.homework.AliasActivityPoem

//com.yumc.phsuperapp/com.yum.ph.SplashAct (必胜客)
//com.mcdonalds.gma.cn/com.mcdonalds.gma.cn.activity.LaunchActivity （麦当劳）

//com.mxbc.mxsa/com.mxbc.mxsa.modules.splash.SplashActivity （蜜雪冰城）

//com.tencent.weread/com.tencent.weread.LauncherActivity
//com.showstartfans.activity/com.showstartfans.activity.activitys.welcome.WelcomeNewActivity
//cn.dxy.android.aspirin/cn.dxy.android.aspirin.startup.StartupActivity

//com.piaoyou.piaoxingqiu/com.piaoyou.piaoxingqiu.home.loading.LoadingActivity
//com.qidian.QDReader/com.qidian.QDReader.ui.activity.SplashActivity



public class ScreenCaptureImageActivity extends Activity {


    private static final String TAG = ScreenCaptureImageActivity.class.getName();
    private static final int REQUEST_CODE = 100;
    public static String STORE_DIRECTORY;
    private static int IMAGES_PRODUCED;
    private static final String SCREENCAP_NAME = "screencap";
    private static final int VIRTUAL_DISPLAY_FLAGS = DisplayManager.VIRTUAL_DISPLAY_FLAG_OWN_CONTENT_ONLY | DisplayManager.VIRTUAL_DISPLAY_FLAG_PUBLIC;
    private static MediaProjection sMediaProjection;

    private MediaProjectionManager mProjectionManager;
    private static ImageReader mImageReader;
    private Handler mHandler;
    private Display mDisplay;
    private VirtualDisplay mVirtualDisplay;
    private int mDensity;
    private static int mWidth;
    private static int mHeight;
    private static int mRotation;
    private OrientationChangeCallback mOrientationChangeCallback;
    private static Bitmap lastBitmap;

    public static Bitmap getImage()
    {
        Image image = null;
        FileOutputStream fos = null;
        Bitmap bitmap = null;

        if(mImageReader==null)
            return null;
        try {
            image = mImageReader.acquireLatestImage();
            if (image != null) {
                Image.Plane[] planes = image.getPlanes();
                ByteBuffer buffer = planes[0].getBuffer();
                int pixelStride = planes[0].getPixelStride();
                int rowStride = planes[0].getRowStride();
                int rowPadding = rowStride - pixelStride * mWidth;

                // create bitmap
                bitmap = Bitmap.createBitmap(mWidth + rowPadding / pixelStride, mHeight, Bitmap.Config.ARGB_8888);
                bitmap.copyPixelsFromBuffer(buffer);

                bitmap = Bitmap.createBitmap(bitmap,0,0,mWidth,mHeight);
                IMAGES_PRODUCED++;
                Log.e(TAG, "captured image: " + IMAGES_PRODUCED);
            }

        } catch (Exception e) {
            e.printStackTrace();
        }finally
        {
            if (image != null) {
                    image.close();
                }
        }
        if(lastBitmap!=null)
        {
            lastBitmap.recycle();
            lastBitmap = null;
        }
        if(bitmap!=null)
            lastBitmap = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        return bitmap;
    }

    public static void saveScreenshot(String filepath,int ratio)/*0-100*/
    {
        try
        {
            if (getImage() != null)
            {
                FileOutputStream fos = null;
                double RECORD_PRODUCEDS = System.currentTimeMillis();
                File storeDirectory = new File(filepath);
                if (!storeDirectory.exists())
                {
                    boolean success = storeDirectory.mkdirs();
                    if (!success)
                    {
                        Log.e("error", "failed to create file storage directory.");
                        return;
                    }
                }
                Log.d("save one image", filepath + RECORD_PRODUCEDS);
                fos = new FileOutputStream(filepath + RECORD_PRODUCEDS + "_src.png");
                lastBitmap.compress(Bitmap.CompressFormat.JPEG, ratio, fos);
                fos.close();
            }
        }catch (Exception e)
        {
            e.printStackTrace();
        }
    }

    private class ImageAvailableListener implements ImageReader.OnImageAvailableListener {
        @Override
        public void onImageAvailable(ImageReader reader) {
//            Image image = null;
//            FileOutputStream fos = null;
//            Bitmap bitmap = null;
//
//            try {
//                image = reader.acquireLatestImage();
//                if (image != null) {
//                    Image.Plane[] planes = image.getPlanes();
//                    ByteBuffer buffer = planes[0].getBuffer();
//                    int pixelStride = planes[0].getPixelStride();
//                    int rowStride = planes[0].getRowStride();
//                    int rowPadding = rowStride - pixelStride * mWidth;
//
//                    // create bitmap
//                    bitmap = Bitmap.createBitmap(mWidth + rowPadding / pixelStride, mHeight, Bitmap.Config.ARGB_8888);
//                    bitmap.copyPixelsFromBuffer(buffer);
//
////                    // write bitmap to a file
////                    fos = new FileOutputStream(STORE_DIRECTORY + "/myscreen_" + IMAGES_PRODUCED + ".png");
////                    bitmap.compress(CompressFormat.JPEG, 100, fos);
//
//                    IMAGES_PRODUCED++;
//                    Log.e(TAG, "captured image: " + IMAGES_PRODUCED);
//                }
//
//            } catch (Exception e) {
//                e.printStackTrace();
//            } finally {
//                if (fos != null) {
//                    try {
//                        fos.close();
//                    } catch (IOException ioe) {
//                        ioe.printStackTrace();
//                    }
//                }
//
//                if (bitmap != null) {
//                    bitmap.recycle();
//                }
//
//                if (image != null) {
//                    image.close();
//                }
//            }
        }
    }

    private class OrientationChangeCallback extends OrientationEventListener {

        OrientationChangeCallback(Context context) {
            super(context);
        }

        @Override
        public void onOrientationChanged(int orientation) {
            final int rotation = mDisplay.getRotation();
            if (rotation != mRotation) {
                mRotation = rotation;
                try {
                    // clean up
                    if (mVirtualDisplay != null) mVirtualDisplay.release();
                    if (mImageReader != null) mImageReader.setOnImageAvailableListener(null, null);

                    // re-create virtual display depending on device width / height
                    createVirtualDisplay();
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
        }
    }

    private class MediaProjectionStopCallback extends MediaProjection.Callback {
        @Override
        public void onStop() {
            Log.e("ScreenCapture", "stopping projection.");
            mHandler.post(new Runnable() {
                @Override
                public void run() {
                    if (mVirtualDisplay != null) mVirtualDisplay.release();
                    if (mImageReader != null) mImageReader.setOnImageAvailableListener(null, null);
                    if (mOrientationChangeCallback != null) mOrientationChangeCallback.disable();
                    sMediaProjection.unregisterCallback(MediaProjectionStopCallback.this);
                }
            });
        }
    }

    /****************************************** Activity Lifecycle methods ************************/
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
//        setContentView(R.layout.activity_main);

        // call for the projection manager
        mProjectionManager = (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        startProjection();

        // start capture handling thread
        new Thread() {
            @Override
            public void run() {
                Looper.prepare();
                mHandler = new Handler();
                Looper.loop();
            }
        }.start();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == REQUEST_CODE) {
            sMediaProjection = mProjectionManager.getMediaProjection(resultCode, data);
            if (sMediaProjection != null) {
                File externalFilesDir = getExternalFilesDir(null);
                if (externalFilesDir != null) {
                    STORE_DIRECTORY = externalFilesDir.getAbsolutePath();
                    File storeDirectory = new File(STORE_DIRECTORY+"/screenshots/");
                    if (!storeDirectory.exists()) {
                        boolean success = storeDirectory.mkdirs();
                        if (!success) {
                            Log.e(TAG, "failed to create file storage directory.");
                            return;
                        }
                    }
                } else {
                    Log.e(TAG, "failed to create file storage directory, getExternalFilesDir is null.");
                    return;
                }

                // display metrics
                DisplayMetrics metrics = getResources().getDisplayMetrics();
                mDensity = metrics.densityDpi;
                mDisplay = getWindowManager().getDefaultDisplay();

                // create virtual display depending on device width / height
                createVirtualDisplay();

                // register orientation change callback
                mOrientationChangeCallback = new OrientationChangeCallback(this);
                if (mOrientationChangeCallback.canDetectOrientation()) {
                    mOrientationChangeCallback.enable();
                }

                // register media projection stop callback
                sMediaProjection.registerCallback(new MediaProjectionStopCallback(), mHandler);
            }

            String pkg;
            String cls;

            SharedPreferences sharedPref = getSharedPreferences("Data", MODE_PRIVATE);
            pkg= sharedPref.getString("package", null);
            cls= sharedPref.getString("startClass", null);

            Intent intent = new Intent();
            //intent.setClassName("com.mtr.mtrmobile", "com.mtr.mtrmobile.MTRMobileActivity");
            intent.setClassName(pkg, cls);
            RecordService.isStartCrawl=true;
            startActivity(intent);
        }
    }

    /****************************************** UI Widget Callbacks *******************************/
    private void startProjection() {
        startActivityForResult(mProjectionManager.createScreenCaptureIntent(), REQUEST_CODE);
        JSONObject obj = new JSONObject();
        /*try {
            obj.put("username",Utility.USER);
            obj.put("timestamp",System.currentTimeMillis());
            obj.put("status","startProjection");
            MediaType jsonType = MediaType.parse("application/json; charset=utf-8");
            Utility.post("/switch", RequestBody.create(jsonType, obj.toString()));
        }catch (Exception e)
        {
            e.printStackTrace();
        }*/
    }

    private void stopProjection() {
        mHandler.post(new Runnable() {
            @Override
            public void run() {
                if (sMediaProjection != null) {
                    sMediaProjection.stop();
                }
            }
        });
    }

    /****************************************** Factoring Virtual Display creation ****************/
    private void createVirtualDisplay() {
        // get width and height
        Point size = new Point();
        mDisplay.getRealSize(size);
        mWidth = size.x;
        mHeight = size.y;

        // start capture reader
        mImageReader = ImageReader.newInstance(mWidth, mHeight, PixelFormat.RGBA_8888, 2);
        mVirtualDisplay = sMediaProjection.createVirtualDisplay(SCREENCAP_NAME, mWidth, mHeight, mDensity, VIRTUAL_DISPLAY_FLAGS, mImageReader.getSurface(), null, mHandler);
    }

    @Override
    protected void onDestroy()
    {
        stopProjection();
        super.onDestroy();
    }
}